import re
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.security import verify_password
from pydantic import ValidationError

SEED_SQL = Path(__file__).resolve().parents[3] / "infra/postgres/seed/seed_data.sql"
SEED_PASSWORD = "envelo-dev-password"  # documented in seed_data.sql and the README


def _settings(**overrides) -> Settings:
    values = {
        "postgres_user": "u",
        "postgres_password": "p",
        "postgres_db": "d",
        "statement_upload_dir": "/tmp",
        "jwt_secret": "x" * 32,
    }
    values.update(overrides)
    # _env_file=None: judge exactly these values, not whatever .env holds.
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("secret", ["change_me", "x" * 31, ""])
def test_a_weak_jwt_secret_stops_startup(secret, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="JWT_SECRET must be at least 32 characters"):
        _settings(jwt_secret=secret)


def test_a_32_character_secret_is_accepted(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    assert _settings(jwt_secret="x" * 32).jwt_secret.get_secret_value() == "x" * 32


def test_the_seeded_hash_matches_the_documented_password():
    # The seed file says which password signs in; if the hash and the comment
    # ever drift apart, the demo account silently stops working.
    password_hash = re.search(r"'(\$argon2id\$[^']+)'", SEED_SQL.read_text()).group(1)
    assert verify_password(SEED_PASSWORD, password_hash)
