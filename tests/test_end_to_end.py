"""The assignment's sample payment against a freshly created database."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

import taxdome.main as main
from taxdome.db import Base
from taxdome.models import Firm, Payment
from taxdome.seed import seed_sample_firms


def test_sample_payment_on_fresh_database(database_engines, monkeypatch):
    _, test_engine = database_engines
    database_name = f"taxdome_e2e_{uuid4().hex}"
    admin = create_engine(test_engine.url, isolation_level="AUTOCOMMIT")
    fresh_engine = None

    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        fresh_engine = create_engine(test_engine.url.set(database=database_name))
        Base.metadata.create_all(fresh_engine)
        with Session(fresh_engine) as session, session.begin():
            assert seed_sample_firms(session) == 3

        monkeypatch.setattr(
            main,
            "SessionLocal",
            sessionmaker(bind=fresh_engine, autoflush=False, expire_on_commit=False),
        )
        with TestClient(main.app) as client:
            response = client.post(
                "/api/v1/bulk-payments",
                json={
                    "payer_firm_uuid": "3f1c9a2e-7b4d-4c1e-9a55-2d8e6f0b7c41",
                    "payments": [
                        {
                            "amount": "6250",
                            "payee_firm_uuid": "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25",
                            "description": "Overflow returns, August 2026",
                        },
                        {
                            "amount": "5800.5",
                            "payee_firm_uuid": "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25",
                            "description": "Amended returns, August 2026",
                        },
                        {
                            "amount": "1200.75",
                            "payee_firm_uuid": "8b2e4c71-0d3a-4f6e-b1c9-5a7d2e9f4c10",
                            "description": "Bookkeeping cleanup, 3 clients",
                        },
                    ],
                },
            )

        assert response.status_code == 201
        payments = response.json()["payments"]
        assert [payment["amount"] for payment in payments] == [
            "6250.00", "5800.50", "1200.75"
        ]
        assert len({payment["id"] for payment in payments}) == 3

        with Session(fresh_engine) as session:
            balances = {firm.name: firm.balance_cents for firm in session.scalars(select(Firm))}
            stored_payments = session.scalars(select(Payment)).all()
        assert balances == {
            "Pinecrest CPA Group": 3_674_875,
            "Lopez Bookkeeping": 170_075,
            "Nair Tax Services": 1_405_050,
        }
        assert len(stored_payments) == 3
    finally:
        if fresh_engine is not None:
            fresh_engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        admin.dispose()
