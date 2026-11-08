"""Access-token checks on the protected /budget/* routes (#37).

Uses `anon_client`, which does *not* override `get_current_user_id`: every
request here goes through the real JWT verification.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import ALGORITHM, AUDIENCE, ISSUER, create_access_token
from app.db.repositories.constants import SEED_USER_ID
from app.main import app
from fastapi.routing import APIRoute

PROTECTED_PROBE = "/budget/transactions"  # answers [] rather than 404 when empty


def _token(**overrides) -> str:
    """A token signed with the real secret, with claims overridden (or removed,
    by passing None) - so each test breaks exactly one thing about it."""
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(SEED_USER_ID),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "aud": AUDIENCE,
        "iss": ISSUER,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm=ALGORITHM)


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _budget_routes() -> list[tuple[str, str]]:
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/budget"):
            # Any well-formed id will do: the request must be refused before
            # anything looks it up.
            path = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), route.path)
            routes.extend((method, path) for method in route.methods)
    return routes


@pytest.mark.parametrize(("method", "path"), _budget_routes())
async def test_every_budget_route_requires_a_token(anon_client, method, path):
    response = await anon_client.request(method, path)
    assert response.status_code == 401, f"{method} {path} answered {response.status_code}"
    assert response.headers["www-authenticate"] == "Bearer"


async def test_the_route_list_is_not_empty():
    # Guards the parametrized test above: if `_budget_routes` ever found
    # nothing, it would pass by testing zero routes.
    assert len(_budget_routes()) > 30


async def test_public_routes_stay_public(anon_client):
    assert (await anon_client.get("/health")).status_code == 200
    # Reaches the handler (and fails on the credentials), rather than 401-ing
    # for want of a token it cannot have yet.
    login = await anon_client.post("/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert login.json()["detail"] == "Invalid email or password"


async def test_a_valid_token_is_accepted(anon_client):
    response = await anon_client.get(PROTECTED_PROBE, headers=_bearer(create_access_token(SEED_USER_ID)))
    assert response.status_code == 200


async def test_a_token_from_login_is_accepted(anon_client):
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    pair = (await anon_client.post("/auth/register", json={"email": email, "password": "correct horse battery"})).json()

    response = await anon_client.get(PROTECTED_PROBE, headers=_bearer(pair["access_token"]))
    assert response.status_code == 200


async def test_wrong_scheme_is_rejected(anon_client):
    # HTTPBearer's own auto_error would answer this with 403; #37 wants 401.
    response = await anon_client.get(PROTECTED_PROBE, headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("not-a-jwt", id="garbage"),
        pytest.param(_token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)), id="expired"),
        pytest.param(_token(aud="someone-else"), id="wrong-audience"),
        pytest.param(_token(iss="someone-else"), id="wrong-issuer"),
        pytest.param(_token(aud=None), id="no-audience"),
        pytest.param(_token(exp=None), id="no-expiry"),
        pytest.param(_token(sub=None), id="no-subject"),
        pytest.param(_token(sub="not-a-uuid"), id="subject-not-a-uuid"),
        pytest.param(
            jwt.encode(
                {"sub": str(SEED_USER_ID), "aud": AUDIENCE, "iss": ISSUER, "iat": 0, "exp": 4102444800},
                "a-different-secret-of-sufficient-length!",
                algorithm=ALGORITHM,
            ),
            id="wrong-signature",
        ),
    ],
)
async def test_bad_tokens_are_rejected(anon_client, token):
    response = await anon_client.get(PROTECTED_PROBE, headers=_bearer(token))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
