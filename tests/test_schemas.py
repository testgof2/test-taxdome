from uuid import UUID

import pytest
from pydantic import ValidationError

from taxdome.schemas import (
    BulkPaymentRequest,
    PaymentRequest,
    amount_to_cents,
)


PAYER_UUID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
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


@pytest.mark.parametrize("amount", ["1.235", "1." + ("0" * 40) + "1"])
def test_amount_rejects_fractional_cents(amount):
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount=amount))


def test_amount_must_be_positive():
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount="0"))


def test_amount_must_be_json_string():
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount=1.25))


def test_amount_must_fit_integer_cents_storage():
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount="21474836.48"))


def test_bulk_request_requires_at_least_one_payment():
    with pytest.raises(ValidationError):
        BulkPaymentRequest.model_validate(
            {"payer_firm_uuid": str(PAYER_UUID), "payments": []}
        )
