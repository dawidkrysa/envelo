import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from app.core.config import get_settings
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

ph = PasswordHasher()
ALGORITHM = "HS256"
ISSUER = AUDIENCE = "envelo-api-gateway"

settings = get_settings()


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    sub = str(user_id)
    iat = datetime.now(timezone.utc)
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    aud = AUDIENCE
    iss = ISSUER

    return jwt.encode(
        {"sub": sub, "iat": iat, "exp": exp, "aud": aud, "iss": iss},
        settings.jwt_secret.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> uuid.UUID:
    payload = jwt.decode(
        token, settings.jwt_secret.get_secret_value(), algorithms=[ALGORITHM], audience=AUDIENCE, issuer=ISSUER
    )
    return uuid.UUID(payload["sub"])


def generate_refresh_token() -> str:
    return token_urlsafe(32)


def hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()
