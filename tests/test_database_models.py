from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import pytest

from taxdome.models import Firm, Payment
from taxdome.seed import seed_sample_firms


def test_firm_uuid_must_be_unique(task2_session):
    task2_session.add_all(
        [
            Firm(id=11, name="First", balance_cents=100, uuid="same-uuid"),
            Firm(id=12, name="Second", balance_cents=100, uuid="same-uuid"),
        ]
    )
    with pytest.raises(IntegrityError):
        task2_session.flush()


def test_payment_firm_ids_must_reference_existing_firms(task2_session):
    task2_session.add(
        Payment(
            payer_firm_id=101,
            payee_firm_id=102,
            amount_cents=1,
            description="invalid references",
        )
    )
    with pytest.raises(IntegrityError):
        task2_session.flush()


def test_firm_balance_cannot_be_negative(task2_session):
    task2_session.add(
        Firm(id=13, name="Negative balance", balance_cents=-1, uuid="negative")
    )
    with pytest.raises(IntegrityError):
        task2_session.flush()


def test_payment_amount_must_be_positive(task2_session):
    task2_session.add(
        Firm(id=14, name="Payer", balance_cents=100, uuid="payer")
    )
    task2_session.add(
        Firm(id=15, name="Payee", balance_cents=100, uuid="payee")
    )
    task2_session.flush()
    task2_session.add(
        Payment(
            payer_firm_id=14,
            payee_firm_id=15,
            amount_cents=0,
            description="zero amount",
        )
    )
    with pytest.raises(IntegrityError):
        task2_session.flush()


def test_seed_inserts_exact_sample_firms(task2_session):
    assert seed_sample_firms(task2_session) == 3
    firms = task2_session.scalars(select(Firm).order_by(Firm.id)).all()

    assert [
        (firm.id, firm.name, firm.balance_cents, firm.uuid) for firm in firms
    ] == [
        (1, "Pinecrest CPA Group", 5_000_000, "3f1c9a2e-7b4d-4c1e-9a55-2d8e6f0b7c41"),
        (2, "Lopez Bookkeeping", 50_000, "8b2e4c71-0d3a-4f6e-b1c9-5a7d2e9f4c10"),
        (3, "Nair Tax Services", 200_000, "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25"),
    ]


def test_rerunning_seed_preserves_existing_firm_data(task2_session):
    assert seed_sample_firms(task2_session) == 3
    task2_session.flush()
    firm = task2_session.get(Firm, 1)
    assert firm is not None
    firm.name = "Renamed by user"
    firm.balance_cents = 123_456
    task2_session.commit()

    assert seed_sample_firms(task2_session) == 0
    task2_session.refresh(firm)
    assert firm.name == "Renamed by user"
    assert firm.balance_cents == 123_456
    assert task2_session.scalar(select(Firm.id).where(Firm.id == 4)) is None


def test_firm_ids_continue_after_seed(task2_session):
    assert seed_sample_firms(task2_session) == 3
    firm = Firm(name="Later firm", balance_cents=10, uuid="later-firm")
    task2_session.add(firm)
    task2_session.flush()

    assert firm.id == 4
