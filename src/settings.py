"""Centralised runtime settings (kernel).

Single typed entry point for environment-driven configuration (anonymisation salt, database
connection), read from the process environment and the project ``.env`` via *pydantic-settings*.
Replaces scattered ``os.environ.get`` calls. Depends only on the shared kernel (``src.config``).
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from src import config

_PLACEHOLDER_SALT = "change-me-with-a-long-random-secret"


class Settings(BaseSettings):
    """Environment / ``.env`` configuration (env vars take precedence over the file)."""

    model_config = SettingsConfigDict(
        env_file=config.PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Anonymisation (operator PII pseudonymisation).
    anonymization_salt: str = ""
    pseudonym_length: int = config.DEFAULT_PSEUDONYM_LENGTH

    # PostgreSQL (defaults match docker-compose.yml).
    postgres_user: str = "predictive"
    postgres_password: str = "predictive"
    postgres_db: str = "predictive_maintenance"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the PostgreSQL database."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def salt_configured(self) -> bool:
        """True if a real anonymisation salt is set (not empty / not the placeholder)."""
        salt = self.anonymization_salt.strip()
        return bool(salt) and salt != _PLACEHOLDER_SALT


def get_settings() -> Settings:
    """Read the current settings from the environment / ``.env`` (cheap; call where needed)."""
    return Settings()


def require_salt() -> str:
    """Return the anonymisation salt, failing fast with a clear message if unconfigured."""
    settings = get_settings()
    if not settings.salt_configured:
        raise SystemExit(
            "ANONYMIZATION_SALT is missing or not configured in .env — operator PII "
            "pseudonymisation requires a real salt (see .env.example)."
        )
    return settings.anonymization_salt
