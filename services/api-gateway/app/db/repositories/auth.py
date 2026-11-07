"""Users and refresh tokens (#37).

Unlike the other repositories, nothing here raises `HTTPException`: every
failure comes back as `None` and the router in `app/main.py` turns it into a
status code. Auth failures must all look alike from outside - one message, one
`WWW-Authenticate: Bearer` header - and that is easier to guarantee in one
place than in every branch below.

Refresh tokens are opaque random strings; only their SHA-256 hash is stored,
so a leaked copy of the table cannot be replayed. Each login starts a token
*family* (`family_id`) that every rotation of that session inherits, which is
what lets a detected replay revoke the whole session in one UPDATE.
"""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.security import create_access_token, generate_refresh_token, hash_password, hash_token, verify_password
from app.db.models import RefreshToken, User
from app.schemas.auth import TokenPair
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Verified against when a login names an unknown email, so that path spends the
# same Argon2 time as a wrong password (see `authenticate_user`). Hashed once at
# import, from a random value: it belongs to no account, so nothing can match it.
DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


async def create_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Create a user with an Argon2id hash of `password`.

    Returns the new user, or `None` if the email is already registered.
    `email` arrives normalized (stripped, lower-cased) by the request schema.

    Duplicates are caught by the unique constraint on commit rather than by
    looking the email up first - a look-up-then-insert lets two simultaneous
    registrations both pass the check. The failed commit is rolled back, since
    a session whose commit failed refuses all further work until it is.
    """
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return None
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """Return the user if `email` exists and `password` matches, else `None`.

    "No such email" and "wrong password" are indistinguishable: same return
    value and the same Argon2 work. Skipping verification for an unknown email
    would answer it measurably faster, and a stopwatch would then reveal which
    addresses have an account. Read-only - no commit.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        verify_password(password, DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def _add_refresh_token(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID) -> tuple[RefreshToken, str]:
    """Stage a new refresh token in `family_id`; return the row and the raw token.

    Flushes but does not commit: `rotate_refresh_token` has to commit the new
    token together with the revocation of the old one. The flush is also what
    assigns `row.id` (a Python-side default fills in on INSERT, not on
    construction), which rotation needs for `replaced_by_id`.
    """
    raw = generate_refresh_token()
    now = datetime.now(timezone.utc)

    row = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_token(raw),
        expires_at=now + timedelta(days=get_settings().jwt_refresh_token_expire_days),
    )
    db.add(row)
    await db.flush()
    return row, raw


async def issue_token_pair(db: AsyncSession, user_id: uuid.UUID, family_id: uuid.UUID | None = None) -> TokenPair:
    """Issue an access token and a refresh token for `user_id`, and commit.

    Without `family_id` (register, login) this starts a new session. Each login
    is its own family, so revoking one session - e.g. on a detected replay -
    leaves the user's other devices logged in.
    """
    _, raw = await _add_refresh_token(db, user_id, family_id or uuid.uuid4())
    await db.commit()
    return TokenPair(access_token=create_access_token(user_id), refresh_token=raw)


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> TokenPair | None:
    """Exchange a valid refresh token for a new pair; `None` if it isn't valid.

    Unknown, expired, revoked and replayed tokens all return the same `None`,
    which the router answers with the same 401.

    - The row is read `FOR UPDATE`, so two concurrent refreshes of one token run
      one after the other: the second sees the first's `revoked_at` rather than
      both issuing a pair and forking the session. `populate_existing` makes
      that read overwrite any copy already in the session's identity map -
      otherwise the lock is taken but a stale `revoked_at` is what gets checked.
    - A token that is already revoked is a replay: it was rotated or logged out
      before, so someone is reusing a copy. Every still-active token in its
      family is revoked, and that is committed even though the call fails -
      otherwise the revocation would be discarded with the session.
    - A valid token is revoked and replaced in a single commit. Separate commits
      would leave the user with no valid token if the second one never ran.
    """
    now = datetime.now(timezone.utc)
    row = (
        await db.execute(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_token(raw_token))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()

    if row is None:
        return None

    if row.revoked_at is not None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.commit()
        return None

    if row.expires_at <= now:
        return None

    new_row, raw = await _add_refresh_token(db, row.user_id, row.family_id)
    row.revoked_at = now
    row.replaced_by_id = new_row.id
    await db.commit()
    return TokenPair(access_token=create_access_token(row.user_id), refresh_token=raw)


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke one refresh token (logout); a no-op if it isn't an active token.

    A single UPDATE with no select first: an unknown or already-revoked token
    simply matches 0 rows, which is the idempotent behaviour logout needs.

    Only this token is revoked, not its family - logging out is the normal end
    of a session, not a theft signal. Reusing the token later still hits the
    replay branch of `rotate_refresh_token`, which takes the family down then.
    """
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
