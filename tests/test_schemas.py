from uuid import UUID

import pytest
from pydantic import ValidationError

from taxdome.schemas import (
    PaymentRequest,
    amount_to_cents,
)


PAYEE_UUID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def payment_data(**overrides):
    values = {
        "payee_firm_uuid": str(PAYEE_UUID),
        "amount": "300.00",
        "description": "Monthly accounting",
    }
    values.update(overrides)
    return values


def test_positive_amount_strings_convert_to_exact_cents():
    whole_dollar = PaymentRequest.model_validate(payment_data(amount="300"))
    trailing_zeroes = PaymentRequest.model_validate(payment_data(amount="1.2300"))

    assert amount_to_cents(whole_dollar.amount) == 30_000
    assert amount_to_cents(trailing_zeroes.amount) == 123


def test_amount_rejects_fractional_cents():
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount="1.235"))
