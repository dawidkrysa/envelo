from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str
    # Password string where the value is kept partially secret
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    log_level: str = "INFO"

    max_upload_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    allowed_statement_formats: str = "csv"
    statement_upload_dir: str
    jwt_secret: SecretStr
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_is_strong(cls, v: SecretStr) -> SecretStr:
        # Anyone who knows (or guesses) this can sign a token for any user, so
        # a weak one must stop the app at startup - not let it run looking
        # healthy. 32 characters is RFC 7518's floor for HS256's 256-bit key;
        # it also rejects the `change_me` placeholder from .env.example.
        if len(v.get_secret_value()) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters. Generate one with: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


# Automatically caches the results of function calls.
@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
