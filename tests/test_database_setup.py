from sqlalchemy import text

from taxdome.db import SessionLocal


def test_development_and_test_databases_are_separate(database_engines) -> None:
    dev_engine, test_engine = database_engines

    assert dev_engine.url.database != test_engine.url.database

    with dev_engine.connect() as connection:
        dev_database = connection.scalar(text("SELECT current_database()"))
    with SessionLocal(bind=test_engine) as session:
        test_database = session.scalar(text("SELECT current_database()"))

    assert dev_database == dev_engine.url.database
    assert test_database == test_engine.url.database
