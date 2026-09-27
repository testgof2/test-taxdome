"""Typed request and response DTOs for the REST API."""

import re
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PLAIN_DECIMAL = re.compile(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")
MAX_BALANCE_CENTS = 2_147_483_647


def amount_to_cents(amount: str) -> int:
    """Convert a positive plain decimal amount to cents without rounding."""
    if not isinstance(amount, str) or _PLAIN_DECIMAL.fullmatch(amount) is None:
        raise ValueError("amount must be a plain decimal string")

    try:
        decimal_amount = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError("amount must be a plain decimal string") from exc

    if not decimal_amount.is_finite() or decimal_amount <= 0:
        raise ValueError("amount must be greater than zero")

    numerator, denominator = decimal_amount.as_integer_ratio()
    cents, remainder = divmod(numerator * 100, denominator)
    if remainder:
        raise ValueError("amount must be an exact number of cents")
    if cents < 1 or cents > MAX_BALANCE_CENTS:
        raise ValueError("amount is outside the supported cents range")
    return cents


def cents_to_amount(cents: int) -> str:
    """Format a positive integer-cent payment as a two-decimal amount."""
    if type(cents) is not int or not 1 <= cents <= MAX_BALANCE_CENTS:
        raise ValueError("cents is outside the supported range")
    return f"{cents // 100}.{cents % 100:02d}"


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PaymentRequest(StrictDTO):
    payee_firm_uuid: UUID
    amount: Annotated[str, Field(strict=True)]
    description: Annotated[str, Field(strict=True)]

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive_decimal_string(cls, value: str) -> str:
        amount_to_cents(value)
        return value


class BulkPaymentRequest(StrictDTO):
    payer_firm_uuid: UUID
    payments: list[PaymentRequest] = Field(min_length=1)


class PaymentResponse(StrictDTO):
    id: int
    payee_firm_uuid: UUID
    amount: str
    description: str


class BulkPaymentResponse(StrictDTO):
    payer_firm_uuid: UUID
    payments: list[PaymentResponse]


class ErrorDetail(StrictDTO):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(StrictDTO):
    detail: list[ErrorDetail]
