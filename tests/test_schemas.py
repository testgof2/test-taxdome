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


@pytest.mark.parametrize("amount", ["1e2", " 1"])
def test_amount_rejects_non_decimal_notation(amount):
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount=amount))


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


def test_bulk_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        BulkPaymentRequest.model_validate(
            {
                "payer_firm_uuid": str(PAYER_UUID),
                "payments": [payment_data()],
                "unexpected": True,
            }
        )


def test_bulk_request_preserves_duplicate_recipients_as_separate_payments():
    request = BulkPaymentRequest.model_validate(
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [
                payment_data(amount="1.10", description="First transfer"),
                payment_data(amount="2.20", description="Second transfer"),
            ],
        }
    )

    assert [payment.payee_firm_uuid for payment in request.payments] == [
        PAYEE_UUID,
        PAYEE_UUID,
    ]
    assert [payment.description for payment in request.payments] == [
        "First transfer",
        "Second transfer",
    ]


def test_payment_description_may_be_empty():
    payment = PaymentRequest.model_validate(payment_data(description=""))

    assert payment.description == ""
