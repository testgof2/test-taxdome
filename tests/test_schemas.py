from uuid import UUID

import pytest
from pydantic import ValidationError

from taxdome.schemas import (
    BulkPaymentRequest,
    BulkPaymentResponse,
    ErrorDetail,
    ErrorResponse,
    PaymentRequest,
    PaymentResponse,
    amount_to_cents,
    cents_to_amount,
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


@pytest.mark.parametrize(
    ("amount", "expected_cents"),
    [
        ("300", 30_000),
        ("5800.5", 580_050),
        ("1200.75", 120_075),
        ("0.01", 1),
        ("1.2300", 123),
        ("0001.230000", 123),
    ],
)
def test_payment_accepts_positive_plain_decimal_strings(amount, expected_cents):
    payment = PaymentRequest.model_validate(payment_data(amount=amount))

    assert payment.amount == amount
    assert payment.payee_firm_uuid == PAYEE_UUID
    assert amount_to_cents(payment.amount) == expected_cents


@pytest.mark.parametrize(
    "amount",
    [
        "0",
        "0.000",
        "-1",
        "+1",
        "NaN",
        "Infinity",
        "1e2",
        "1.2.3",
        " 1",
        "1 ",
        "",
        "1.235",
        "0.001",
        "1.23" + ("0" * 40) + "1",
        "21474836.48",
    ],
)
def test_payment_rejects_invalid_or_nonpositive_amounts(amount):
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount=amount))


def test_amount_must_be_a_json_string():
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(payment_data(amount=1.25))


@pytest.mark.parametrize(
    ("cents", "formatted"),
    [(1, "0.01"), (123, "1.23"), (2_147_483_647, "21474836.47")],
)
def test_cents_to_amount_formats_two_decimal_places(cents, formatted):
    assert cents_to_amount(cents) == formatted


def test_bulk_request_preserves_duplicate_recipients_and_descriptions():
    request = BulkPaymentRequest.model_validate(
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [
                payment_data(amount="1.10", description="First transfer"),
                payment_data(amount="2.20", description="Second transfer"),
            ],
        }
    )

    assert request.payer_firm_uuid == PAYER_UUID
    assert [payment.payee_firm_uuid for payment in request.payments] == [
        PAYEE_UUID,
        PAYEE_UUID,
    ]
    assert [payment.description for payment in request.payments] == [
        "First transfer",
        "Second transfer",
    ]


@pytest.mark.parametrize(
    "data",
    [
        {"payer_firm_uuid": "bad", "payments": [payment_data()]},
        {"payer_firm_uuid": None, "payments": [payment_data()]},
        {"payments": [payment_data()]},
        {"payer_firm_uuid": str(PAYER_UUID), "payments": []},
        {"payer_firm_uuid": str(PAYER_UUID), "payments": None},
        {"payer_firm_uuid": str(PAYER_UUID), "payments": "not a list"},
        {"payer_firm_uuid": str(PAYER_UUID), "payments": [None]},
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(payee_firm_uuid="bad")],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(payee_firm_uuid=None)],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [{"amount": "1.00", "description": "Missing payee"}],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [{"payee_firm_uuid": str(PAYEE_UUID), "description": "Missing amount"}],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(amount=None)],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(unexpected="value")],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(description=None)],
        },
        {
            "payer_firm_uuid": str(PAYER_UUID),
            "payments": [payment_data(description=7)],
        },
        {"payer_firm_uuid": str(PAYER_UUID), "payments": [payment_data()], "extra": 1},
    ],
)
def test_bulk_request_rejects_malformed_fields_and_unknown_fields(data):
    with pytest.raises(ValidationError):
        BulkPaymentRequest.model_validate(data)


def test_payment_description_is_required_but_may_be_empty():
    payment = PaymentRequest.model_validate(payment_data(description=""))
    assert payment.description == ""

    values = payment_data()
    del values["description"]
    with pytest.raises(ValidationError):
        PaymentRequest.model_validate(values)


def test_bulk_response_serializes_explicit_dtos():
    response = BulkPaymentResponse(
        payer_firm_uuid=PAYER_UUID,
        payments=[
            PaymentResponse(
                id=17,
                payee_firm_uuid=PAYEE_UUID,
                amount="1.10",
                description="Transfer",
            )
        ],
    )

    assert response.model_dump(mode="json") == {
        "payer_firm_uuid": str(PAYER_UUID),
        "payments": [
            {
                "id": 17,
                "payee_firm_uuid": str(PAYEE_UUID),
                "amount": "1.10",
                "description": "Transfer",
            }
        ],
    }


def test_error_dto_has_typed_detail_entries():
    error = ErrorResponse(
        detail=[
            ErrorDetail(code="invalid_amount", message="Amount is invalid", field="amount"),
            ErrorDetail(code="invalid_request", message="Request is invalid"),
        ]
    )

    assert error.model_dump() == {
        "detail": [
            {"code": "invalid_amount", "message": "Amount is invalid", "field": "amount"},
            {"code": "invalid_request", "message": "Request is invalid", "field": None},
        ]
    }
