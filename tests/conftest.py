from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Connection, Engine, create_engine, text

from taxdome.config import Settings
from taxdome.db import Base
from taxdome import models  # noqa: F401 - register model tables with Base.metadata


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def database_engines(settings: Settings) -> Iterator[tuple[Engine, Engine]]:
    dev_engine = create_engine(settings.database_url, pool_pre_ping=True)
    test_engine = create_engine(settings.test_database_url, pool_pre_ping=True)
    if dev_engine.url.database == test_engine.url.database:
        dev_engine.dispose()
        test_engine.dispose()
        raise RuntimeError(
            "DATABASE_URL and TEST_DATABASE_URL must name separate databases"
        )
    try:
        yield dev_engine, test_engine
    finally:
        dev_engine.dispose()
        test_engine.dispose()


@pytest.fixture
def test_schema(database_engines: tuple[Engine, Engine]) -> Iterator[tuple[Engine, str]]:
    """Create model tables in an isolated temporary test schema."""
    dev_engine, test_engine = database_engines
    if dev_engine.url.database == test_engine.url.database:
        raise RuntimeError("Refusing to create test tables because dev and test DBs are the same")

    schema_name = f"task2_test_{uuid4().hex}"
    with test_engine.connect() as connection:
        current_database = connection.scalar(text("SELECT current_database()"))
        if current_database == dev_engine.url.database:
            raise RuntimeError("Refusing to create test tables in the development database")
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        connection.commit()
        try:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.commit()

            Base.metadata.create_all(connection, checkfirst=False)
            connection.commit()
            yield test_engine, schema_name
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            connection.commit()


@pytest.fixture
def test_connection(test_schema: tuple[Engine, str]) -> Iterator[Connection]:
    engine, schema_name = test_schema
    with engine.connect() as connection:
        connection.execute(text(f'SET search_path TO "{schema_name}"'))
        connection.commit()
        yield connection
