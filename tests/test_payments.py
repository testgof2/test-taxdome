import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from taxdome.models import Firm, Payment
from taxdome.payments import PaymentValidationError, process_bulk_payments
from taxdome.schemas import BulkPaymentRequest


@pytest.fixture
def payment_session(test_schema):
    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        connection.close()


def _add_firms(session: Session, *records: tuple[int, str]):
    firms = [
        Firm(
            name=label,
            balance_cents=balance,
            uuid=f"00000000-0000-0000-0000-{index:012d}",
        )
        for index, (balance, label) in enumerate(records, start=1)
    ]
    session.add_all(firms)
    session.commit()
    return firms


def _request(payer: Firm, *payments: tuple[Firm, str, str]) -> BulkPaymentRequest:
    return BulkPaymentRequest.model_validate(
        {
            "payer_firm_uuid": payer.uuid,
            "payments": [
                {
                    "payee_firm_uuid": payee.uuid,
                    "amount": amount,
                    "description": description,
                }
                for payee, amount, description in payments
            ],
        }
    )


def test_exact_available_balance_succeeds(payment_session):
    payer, payee = _add_firms(payment_session, (500, "payer"), (20, "payee"))

    process_bulk_payments(payment_session, _request(payer, (payee, "5.00", "final")))

    assert payer.balance_cents == 0
    assert payee.balance_cents == 520


def test_stored_uppercase_firm_uuids_can_be_paid(payment_session):
    payer, payee = _add_firms(payment_session, (500, "payer"), (20, "payee"))
    payer.uuid = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    payee.uuid = "BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB"
    payment_session.commit()

    result = process_bulk_payments(
        payment_session, _request(payer, (payee, "1.25", "case-insensitive lookup"))
    )

    assert str(result.payer_firm_uuid) == payer.uuid.lower()
    assert str(result.payments[0].payee_firm_uuid) == payee.uuid.lower()
    assert (payer.balance_cents, payee.balance_cents) == (375, 145)
    assert payment_session.scalar(select(func.count()).select_from(Payment)) == 1


def test_locked_firm_refreshes_balance_already_loaded_in_session(payment_session, test_schema):
    payer, first_payee, second_payee = _add_firms(
        payment_session, (100, "payer"), (0, "first payee"), (0, "second payee")
    )
    stale_payer = payment_session.get(Firm, payer.id)
    payment_session.commit()

    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    concurrent_session = Session(bind=connection, expire_on_commit=False)
    try:
        process_bulk_payments(
            concurrent_session,
            _request(payer, (first_payee, "0.80", "committed first")),
        )
    finally:
        concurrent_session.close()
        connection.close()

    assert stale_payer.balance_cents == 100
    with pytest.raises(PaymentValidationError) as error:
        process_bulk_payments(
            payment_session,
            _request(payer, (second_payee, "0.50", "must be rejected")),
        )

    assert error.value.code == "insufficient_funds"
    payment_session.expire_all()
    assert payment_session.get(Firm, payer.id).balance_cents == 20
    assert payment_session.get(Firm, first_payee.id).balance_cents == 80
    assert payment_session.get(Firm, second_payee.id).balance_cents == 0
    assert payment_session.scalar(select(func.count()).select_from(Payment)) == 1


def test_recipient_balance_overflow_rejects_entire_batch(payment_session):
    payer, almost_full, other = _add_firms(
        payment_session, (1_000, "payer"), (2_147_483_640, "almost-full"), (5, "other")
    )

    with pytest.raises(PaymentValidationError) as error:
        process_bulk_payments(
            payment_session,
            _request(payer, (almost_full, "0.08", "would overflow"), (other, "1.00", "would credit")),
        )

    assert error.value.code == "balance_limit_exceeded"
    assert (payer.balance_cents, almost_full.balance_cents, other.balance_cents) == (
        1_000,
        2_147_483_640,
        5,
    )
    assert payment_session.scalar(select(func.count()).select_from(Payment)) == 0


def test_failure_after_flush_rolls_back_balance_and_payment_writes(payment_session, monkeypatch):
    payer, payee = _add_firms(payment_session, (500, "payer"), (20, "payee"))
    real_flush = payment_session.flush

    def flush_then_fail(*args, **kwargs):
        real_flush(*args, **kwargs)
        raise RuntimeError("injected failure after database writes")

    monkeypatch.setattr(payment_session, "flush", flush_then_fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        process_bulk_payments(payment_session, _request(payer, (payee, "5.00", "rollback")))
    monkeypatch.setattr(payment_session, "flush", real_flush)
    payment_session.expire_all()

    assert payment_session.get(Firm, payer.id).balance_cents == 500
    assert payment_session.get(Firm, payee.id).balance_cents == 20
    assert payment_session.scalar(select(func.count()).select_from(Payment)) == 0
