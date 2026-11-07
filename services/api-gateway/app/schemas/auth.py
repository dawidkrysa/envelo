from pydantic import BaseModel, EmailStr, Field, field_validator


class _Credentials(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        # Postgres compares text case-sensitively, so without this "Jan@x.com"
        # and "jan@x.com" would be two accounts. Done here rather than in the
        # repository so register and login cannot normalize differently.
        # Runs after EmailStr has validated the address.
        return v.strip().lower()


class UserRegister(_Credentials):
    password: str = Field(min_length=12, max_length=128)


class UserLogin(_Credentials):
    # No minimum on login: a too-short password just fails to verify (401).
    # A 422 would expose the policy, and lock out anyone whose password
    # predates a stricter one. The maximum stays - it caps Argon2's cost.
    password: str = Field(max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
