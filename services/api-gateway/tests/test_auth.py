"""Auth endpoints (#37): register, login, refresh rotation, logout.

These go through the real token code - nothing here overrides a dependency or
stubs `security.py` - so a token that "works" in these tests works for real.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.core.security import decode_access_token, hash_token
from app.db.models import RefreshToken, User
from sqlalchemy import select, update

PASSWORD = "correct horse battery"


def _email() -> str:
    # Unique per call: the seeded user and other tests must never collide with
    # an address a test expects to be free.
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _register(client, email: str | None = None, password: str = PASSWORD) -> dict:
    response = await client.post("/auth/register", json={"email": email or _email(), "password": password})
    assert response.status_code == 201, response.text
    return response.json()


async def test_register_returns_a_usable_token_pair(client, db_session):
    email = _email()
    pair = await _register(client, email)

    assert pair["token_type"] == "bearer"
    assert pair["refresh_token"]
    # The access token must name the user that was just created, not merely
    # decode: a pair issued for the wrong id would still look valid.
    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    assert decode_access_token(pair["access_token"]) == user.id


async def test_register_stores_a_hash_not_the_password(client, db_session):
    email = _email()
    await _register(client, email)

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    assert user.password_hash != PASSWORD
    assert user.password_hash.startswith("$argon2id$")


async def test_register_rejects_a_taken_email_regardless_of_case(client):
    email = _email()
    await _register(client, email)

    response = await client.post("/auth/register", json={"email": email.upper(), "password": PASSWORD})
    assert response.status_code == 409


async def test_register_rejects_a_short_password(client):
    response = await client.post("/auth/register", json={"email": _email(), "password": "elevenchars"})
    assert response.status_code == 422


async def test_login_with_the_right_password(client):
    email = _email()
    await _register(client, email)

    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_is_case_insensitive_on_email(client):
    email = _email()
    await _register(client, email)

    response = await client.post("/auth/login", json={"email": email.upper(), "password": PASSWORD})
    assert response.status_code == 200


async def test_login_does_not_reveal_whether_the_email_exists(client):
    email = _email()
    await _register(client, email)

    wrong_password = await client.post("/auth/login", json={"email": email, "password": "wrong password!"})
    unknown_email = await client.post("/auth/login", json={"email": _email(), "password": PASSWORD})

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"


async def test_refresh_rotates_the_token(client):
    first = await _register(client)

    response = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]

    # The new token works; the old one is spent.
    assert (await client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})).status_code == 200


async def test_replaying_a_rotated_token_revokes_the_whole_session(client):
    first = await _register(client)
    second = (await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})).json()

    replay = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401

    # The point of the family: `second` was never used, yet it has to die too.
    # Otherwise whoever replayed `first` (or whoever it was stolen from) keeps
    # a live session through the token rotated out of it.
    after = await client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert after.status_code == 401


async def test_replay_does_not_touch_other_sessions(client):
    email = _email()
    phone = await _register(client, email)
    laptop = (await client.post("/auth/login", json={"email": email, "password": PASSWORD})).json()

    await client.post("/auth/refresh", json={"refresh_token": phone["refresh_token"]})
    await client.post("/auth/refresh", json={"refresh_token": phone["refresh_token"]})  # replay

    # Same user, separate login: a different family, so it survives.
    response = await client.post("/auth/refresh", json={"refresh_token": laptop["refresh_token"]})
    assert response.status_code == 200


async def test_expired_refresh_token_is_rejected(client, db_session):
    pair = await _register(client)

    # Back-date it instead of waiting 30 days.
    await db_session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(pair["refresh_token"]))
        .values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    )
    await db_session.commit()

    response = await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert response.status_code == 401


async def test_unknown_refresh_token_is_rejected(client):
    response = await client.post("/auth/refresh", json={"refresh_token": "not-a-token-we-issued"})
    assert response.status_code == 401


async def test_refresh_tokens_are_stored_hashed(client, db_session):
    pair = await _register(client)

    raw = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.token_hash == pair["refresh_token"]))
    ).scalar_one_or_none()
    assert raw is None
    hashed = (
        await db_session.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(pair["refresh_token"])))
    ).scalar_one_or_none()
    assert hashed is not None


async def test_logout_revokes_the_refresh_token(client):
    pair = await _register(client)

    response = await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
    assert response.status_code == 204

    assert (await client.post("/auth/refresh", json={"refresh_token": pair["refresh_token"]})).status_code == 401


async def test_logout_is_idempotent(client):
    pair = await _register(client)
    await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})

    assert (await client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})).status_code == 204
    assert (await client.post("/auth/logout", json={"refresh_token": "never-issued"})).status_code == 204
