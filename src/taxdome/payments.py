"""Atomic bulk payment processing."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from taxdome.models import Firm, Payment
from taxdome.schemas import (
    BulkPaymentRequest,
    BulkPaymentResponse,
    PaymentResponse,
    amount_to_cents,
    cents_to_amount,
)

MAX_INTEGER = 2_147_483_647


class PaymentValidationError(Exception):
    """A business rule failure that an API layer can map to a client error."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def process_bulk_payments(
    session: Session, request: BulkPaymentRequest
) -> BulkPaymentResponse:
    """Transfer a batch atomically, locking all firms in stable ID order."""
    response_payments: list[PaymentResponse]

    with session.begin():
        payer_uuid = str(request.payer_firm_uuid)
        requested_uuids = {payer_uuid}
        for payment_request in request.payments:
            requested_uuids.add(str(payment_request.payee_firm_uuid))

        firms = session.scalars(
            select(Firm)
            .where(Firm.uuid.in_(requested_uuids))
            .order_by(Firm.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        firms_by_uuid = {firm.uuid: firm for firm in firms}

        payer = firms_by_uuid.get(payer_uuid)
        if payer is None:
            raise PaymentValidationError(
                "firm_not_found", "Payer firm was not found", "payer_firm_uuid"
            )

        payee_totals: dict[str, int] = {}
        payment_cents: list[int] = []
        for index, payment_request in enumerate(request.payments):
            payee_uuid = str(payment_request.payee_firm_uuid)
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

            cents = amount_to_cents(payment_request.amount)
            payment_cents.append(cents)
            payee_totals[payee_uuid] = payee_totals.get(payee_uuid, 0) + cents

        total_cents = sum(payment_cents)
        if total_cents > payer.balance_cents:
            raise PaymentValidationError(
                "insufficient_funds", "Payer firm has insufficient funds", "payments"
            )

        for payee_uuid, credit_cents in payee_totals.items():
            if firms_by_uuid[payee_uuid].balance_cents + credit_cents > MAX_INTEGER:
                raise PaymentValidationError(
                    "balance_limit_exceeded",
                    "A payee balance would exceed the supported limit",
                    "payments",
                )

        payer.balance_cents -= total_cents
        for payee_uuid, credit_cents in payee_totals.items():
            firms_by_uuid[payee_uuid].balance_cents += credit_cents

        rows: list[Payment] = []
        for payment_request, cents in zip(request.payments, payment_cents, strict=True):
            row = Payment(
                payer_firm_id=payer.id,
                payee_firm_id=firms_by_uuid[str(payment_request.payee_firm_uuid)].id,
                amount_cents=cents,
                description=payment_request.description,
            )
            session.add(row)
            rows.append(row)

        session.flush()
        response_payments = [
            PaymentResponse(
                id=row.id,
                payee_firm_uuid=payment_request.payee_firm_uuid,
                amount=cents_to_amount(cents),
                description=payment_request.description,
            )
            for row, payment_request, cents in zip(
                rows, request.payments, payment_cents, strict=True
            )
        ]

    return BulkPaymentResponse(
        payer_firm_uuid=request.payer_firm_uuid,
        payments=response_payments,
    )
