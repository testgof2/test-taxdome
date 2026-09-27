from sqlalchemy.exc import IntegrityError
import pytest

from taxdome.models import Firm, Payment


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
