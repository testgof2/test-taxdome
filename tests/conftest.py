from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine

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
