from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from taxdome.config import Settings


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
def migrated_test_schema(database_engines) -> Iterator[tuple[Engine, str]]:
    """Run the initial migration in a blank schema within the test database."""
    dev_engine, test_engine = database_engines
    if dev_engine.url.database == test_engine.url.database:
        raise RuntimeError("Refusing to migrate because dev and test DBs are the same")

    schema_name = f"task2_test_{uuid4().hex}"
    with test_engine.connect() as connection:
        current_database = connection.scalar(text("SELECT current_database()"))
        if current_database == dev_engine.url.database:
            raise RuntimeError("Refusing to migrate the development database")
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        connection.commit()
        try:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.commit()

            alembic_config = Config("alembic.ini")
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")
            connection.commit()
            yield test_engine, schema_name
        finally:
            connection.rollback()
            connection.execute(text("SET search_path TO public"))
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            connection.commit()


@pytest.fixture
def task2_session(migrated_test_schema) -> Iterator[Session]:
    """Give each test a rollback-only transaction in its own migrated schema."""
    engine, schema_name = migrated_test_schema
    with engine.connect() as connection:
        connection.execute(text(f'SET search_path TO "{schema_name}"'))
        connection.commit()
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
