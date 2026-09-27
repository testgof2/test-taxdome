import pytest
from sqlalchemy import text

from taxdome.config import Settings
from taxdome.db import SessionLocal


def test_settings_read_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://example:secret@localhost:55432/example"
    )
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://example:secret@localhost:55432/example_test",
    )
    settings = Settings(_env_file=None)

    assert settings.database_url.endswith("/example")
    assert settings.test_database_url.endswith("/example_test")


def test_development_and_test_databases_are_separate(database_engines) -> None:
    dev_engine, test_engine = database_engines

    assert dev_engine.url.database != test_engine.url.database

    with dev_engine.connect() as connection:
        dev_database = connection.scalar(text("SELECT current_database()"))
    with SessionLocal(bind=test_engine) as session:
        test_database = session.scalar(text("SELECT current_database()"))

    assert dev_database == dev_engine.url.database
    assert test_database == test_engine.url.database
