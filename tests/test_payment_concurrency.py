"""Concurrency guarantees that depend on PostgreSQL row locking."""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Barrier
from time import monotonic, sleep

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from taxdome.models import Firm, Payment
from taxdome.payments import PaymentValidationError, process_bulk_payments
from taxdome.schemas import BulkPaymentRequest


def _firms(session: Session, *balances: int) -> list[Firm]:
    firms = [
        Firm(
            name=f"firm-{index}",
            balance_cents=balance,
            uuid=f"00000000-0000-0000-0000-{index:012d}",
        )
        for index, balance in enumerate(balances, start=1)
    ]
    session.add_all(firms)
    session.commit()
    return firms


def _request(payer: Firm, payee: Firm, amount: str) -> BulkPaymentRequest:
    return BulkPaymentRequest.model_validate(
        {
            "payer_firm_uuid": payer.uuid,
            "payments": [
                {"payee_firm_uuid": payee.uuid, "amount": amount, "description": "concurrent"}
            ],
        }
    )


def _run_while_rows_are_contended(test_schema, locked_uuids, requests):
    """Start independent DB sessions behind a lock, then release them together."""
    engine, schema_name = test_schema
    blocker = engine.connect()
    blocker.execute(text(f'SET search_path TO "{schema_name}"'))
    blocker.commit()
    blocker.execute(
        text(
            "SELECT id FROM firms WHERE uuid = ANY(:uuids) "
            "ORDER BY id FOR UPDATE"
        ),
        {"uuids": locked_uuids},
    )

    barrier = Barrier(len(requests) + 1)
    pids: Queue[int] = Queue()

    def run(request):
        connection = engine.connect()
        try:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(text("SET lock_timeout = '10s'"))
            pids.put(connection.scalar(text("SELECT pg_backend_pid()")))
            connection.commit()
            with Session(bind=connection, expire_on_commit=False) as session:
                barrier.wait(timeout=5)
                try:
                    return process_bulk_payments(session, request)
                except PaymentValidationError as error:
                    return error
        finally:
            connection.close()

    pool = ThreadPoolExecutor(max_workers=len(requests))
    futures = [pool.submit(run, request) for request in requests]
    try:
        try:
            barrier.wait(timeout=5)
            worker_pids = [pids.get(timeout=5) for _ in requests]
            deadline = monotonic() + 3
            while monotonic() < deadline:
                waiting = blocker.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE pid = ANY(:pids) AND wait_event_type = 'Lock'"
                    ),
                    {"pids": worker_pids},
                )
                if waiting == len(requests):
                    break
                sleep(0.02)
            else:
                raise AssertionError("workers did not contend on the locked firms")
        finally:
            blocker.rollback()
            blocker.close()
        return [future.result(timeout=8) for future in futures]
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def _balances(engine, schema_name):
    connection = engine.connect()
    try:
        connection.execute(text(f'SET search_path TO "{schema_name}"'))
        connection.commit()
        with Session(bind=connection) as session:
            balances = {firm.uuid: firm.balance_cents for firm in session.scalars(select(Firm))}
            payment_count = session.scalar(select(func.count()).select_from(Payment))
            total = session.scalar(select(func.sum(Firm.balance_cents)).select_from(Firm))
            return balances, payment_count, total
    finally:
        connection.close()


def test_concurrent_batches_cannot_overspend_one_payer(test_schema):
    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    with Session(bind=connection, expire_on_commit=False) as session:
        payer, recipient_a, recipient_b = _firms(session, 100, 0, 0)
    connection.close()

    results = _run_while_rows_are_contended(
        test_schema,
        [payer.uuid],
        [_request(payer, recipient_a, "0.80"), _request(payer, recipient_b, "0.80")],
    )

    assert sum(not isinstance(result, PaymentValidationError) for result in results) == 1
    errors = [result for result in results if isinstance(result, PaymentValidationError)]
    assert len(errors) == 1 and errors[0].code == "insufficient_funds"
    balances, payment_count, total = _balances(engine, schema_name)
    assert sorted(balances.values()) == [0, 20, 80]
    assert payment_count == 1
    assert total == 100


def test_concurrent_payments_to_shared_recipient_both_credit(test_schema):
    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    with Session(bind=connection, expire_on_commit=False) as session:
        payer_a, payer_b, recipient = _firms(session, 100, 100, 0)
    connection.close()

    results = _run_while_rows_are_contended(
        test_schema,
        [recipient.uuid],
        [_request(payer_a, recipient, "0.80"), _request(payer_b, recipient, "0.70")],
    )

    assert len(results) == 2 and all(not isinstance(r, PaymentValidationError) for r in results)
    balances, payment_count, total = _balances(engine, schema_name)
    assert balances == {payer_a.uuid: 20, payer_b.uuid: 30, recipient.uuid: 150}
    assert payment_count == 2
    assert total == 200


def test_opposing_concurrent_transfers_finish_without_deadlock(test_schema):
    engine, schema_name = test_schema
    connection = engine.connect()
    connection.execute(text(f'SET search_path TO "{schema_name}"'))
    connection.commit()
    with Session(bind=connection, expire_on_commit=False) as session:
        firm_a, firm_b = _firms(session, 100, 100)
    connection.close()

    results = _run_while_rows_are_contended(
        test_schema,
        [firm_a.uuid, firm_b.uuid],
        [_request(firm_a, firm_b, "0.80"), _request(firm_b, firm_a, "0.70")],
    )

    assert len(results) == 2 and all(not isinstance(r, PaymentValidationError) for r in results)
    balances, payment_count, total = _balances(engine, schema_name)
    assert balances == {firm_a.uuid: 90, firm_b.uuid: 110}
    assert payment_count == 2
    assert total == 200
