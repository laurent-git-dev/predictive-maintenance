"""Unit tests for the centralised settings (database URL + salt validation)."""

from __future__ import annotations

from src.settings import Settings


def _settings(**overrides):
    # _env_file=None ignores the project .env; init kwargs override env vars -> deterministic.
    return Settings(_env_file=None, **overrides)


def test_database_url_is_built_from_parts():
    s = _settings(
        postgres_user="u",
        postgres_password="p",
        postgres_db="d",
        postgres_host="h",
        postgres_port=1234,
    )
    assert s.database_url == "postgresql+psycopg2://u:p@h:1234/d"


def test_salt_configured_false_when_empty_or_placeholder():
    assert _settings(anonymization_salt="").salt_configured is False
    assert _settings(anonymization_salt="   ").salt_configured is False
    assert (
        _settings(anonymization_salt="change-me-with-a-long-random-secret").salt_configured is False
    )


def test_salt_configured_true_for_a_real_salt():
    assert _settings(anonymization_salt="a-real-long-secret").salt_configured is True


def test_pseudonym_length_defaults_to_16():
    assert _settings().pseudonym_length == 16
