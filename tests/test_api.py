from collections.abc import Iterator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from taxdome.main import app, get_session
from taxdome.models import Firm, Payment

PINECREST = "3f1c9a2e-7b4d-4c1e-9a55-2d8e6f0b7c41"
LOPEZ = "8b2e4c71-0d3a-4f6e-b1c9-5a7d2e9f4c10"
NAIR = "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25"


@pytest.fixture
def api_context(test_schema) -> Iterator[tuple[TestClient, Session]]:
    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    transaction = connection.begin()
    inspection_session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )

    def override_session() -> Iterator[Session]:
        request_session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield request_session
        finally:
            request_session.close()

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    try:
        yield client, inspection_session
    finally:
        client.close()
        app.dependency_overrides.pop(get_session, None)
        inspection_session.close()
        transaction.rollback()
        connection.close()


def _create_api_test_firms(session: Session) -> None:
    session.add_all(
        [
            Firm(name="Pinecrest CPA Group", balance_cents=5_000_000, uuid=PINECREST),
            Firm(name="Lopez Bookkeeping", balance_cents=50_000, uuid=LOPEZ),
            Firm(name="Nair Tax Services", balance_cents=200_000, uuid=NAIR),
        ]
    )
    session.flush()


def test_insufficient_funds_returns_typed_422_and_keeps_database_unchanged(api_context):
    client, session = api_context
    _create_api_test_firms(session)

    response = client.post(
        "/api/v1/bulk-payments",
        json={
            "payer_firm_uuid": LOPEZ,
            "payments": [
                {"payee_firm_uuid": NAIR, "amount": "500.01", "description": "Too much"}
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "code": "insufficient_funds",
                "message": "Payer firm has insufficient funds",
                "field": "payments",
            }
        ]
    }
    assert {firm.uuid: firm.balance_cents for firm in session.scalars(select(Firm))} == {
        PINECREST: 5_000_000,
        LOPEZ: 50_000,
        NAIR: 200_000,
    }
    assert session.scalar(select(func.count()).select_from(Payment)) == 0


def test_malformed_amount_and_unknown_field_use_typed_422_shape(api_context):
    client, _ = api_context

    response = client.post(
        "/api/v1/bulk-payments",
        json={
            "payer_firm_uuid": PINECREST,
            "payments": [
                {
                    "payee_firm_uuid": NAIR,
                    "amount": "1.235",
                    "description": "Bad precision",
                    "unexpected": True,
                }
            ],
        },
    )

    assert response.status_code == 422
    details = response.json()["detail"]
    assert {(detail["code"], detail["field"]) for detail in details} == {
        ("invalid_request", "payments.0.amount"),
        ("invalid_request", "payments.0.unexpected"),
    }
    assert all(set(detail) == {"code", "message", "field"} for detail in details)
    assert "exact number of cents" in next(
        detail["message"] for detail in details if detail["field"] == "payments.0.amount"
    )
