"""Atomic bulk payment processing."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from taxdome.models import Firm, Payment
from taxdome.schemas import (
    BulkPaymentRequest,
    BulkPaymentResponse,
    MAX_BALANCE_CENTS,
    PaymentResponse,
    amount_to_cents,
    cents_to_amount,
)


class PaymentValidationError(Exception):
    """A business rule failure that an API layer can map to a client error."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def _lock_firms(session: Session, request: BulkPaymentRequest) -> dict[str, Firm]:
    uuids = {str(request.payer_firm_uuid)}
    uuids.update(str(payment.payee_firm_uuid) for payment in request.payments)
    firms = session.scalars(
        select(Firm)
        .where(func.lower(Firm.uuid).in_(uuids))
        .order_by(Firm.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    return {firm.uuid.lower(): firm for firm in firms}


def _validate_batch(
    request: BulkPaymentRequest, firms_by_uuid: dict[str, Firm]
) -> tuple[Firm, list[int], dict[str, int]]:
    payer_uuid = str(request.payer_firm_uuid)
    payer = firms_by_uuid.get(payer_uuid)
    if payer is None:
        raise PaymentValidationError(
            "firm_not_found", "Payer firm was not found", "payer_firm_uuid"
        )

    payee_totals: dict[str, int] = {}
    payment_cents: list[int] = []
    for index, payment in enumerate(request.payments):
        payee_uuid = str(payment.payee_firm_uuid)
        if payee_uuid == payer_uuid:
            raise PaymentValidationError(
                "self_payment", "A firm cannot pay itself", f"payments.{index}.payee_firm_uuid"
            )
        if payee_uuid not in firms_by_uuid:
            raise PaymentValidationError(
                "firm_not_found",
                "Payee firm was not found",
                f"payments.{index}.payee_firm_uuid",
            )

        cents = amount_to_cents(payment.amount)
        payment_cents.append(cents)
        payee_totals[payee_uuid] = payee_totals.get(payee_uuid, 0) + cents

    if sum(payment_cents) > payer.balance_cents:
        raise PaymentValidationError(
            "insufficient_funds", "Payer firm has insufficient funds", "payments"
        )
    for payee_uuid, credit_cents in payee_totals.items():
        if firms_by_uuid[payee_uuid].balance_cents + credit_cents > MAX_BALANCE_CENTS:
            raise PaymentValidationError(
                "balance_limit_exceeded",
                "A payee balance would exceed the supported limit",
                "payments",
            )
    return payer, payment_cents, payee_totals


def process_bulk_payments(
    session: Session, request: BulkPaymentRequest
) -> BulkPaymentResponse:
    """Transfer a batch atomically, locking all firms in stable ID order."""
    with session.begin():
        firms_by_uuid = _lock_firms(session, request)
        payer, payment_cents, payee_totals = _validate_batch(request, firms_by_uuid)

        payer.balance_cents -= sum(payment_cents)
        for payee_uuid, credit_cents in payee_totals.items():
            firms_by_uuid[payee_uuid].balance_cents += credit_cents

        rows = [
            Payment(
                payer_firm_id=payer.id,
                payee_firm_id=firms_by_uuid[str(payment.payee_firm_uuid)].id,
                amount_cents=cents,
                description=payment.description,
            )
            for payment, cents in zip(request.payments, payment_cents, strict=True)
        ]
        session.add_all(rows)
        session.flush()
        response_payments = [
            PaymentResponse(
                id=row.id,
                payee_firm_uuid=payment.payee_firm_uuid,
                amount=cents_to_amount(cents),
                description=payment.description,
            )
            for row, payment, cents in zip(
                rows, request.payments, payment_cents, strict=True
            )
        ]

    return BulkPaymentResponse(
        payer_firm_uuid=request.payer_firm_uuid, payments=response_payments
    )
