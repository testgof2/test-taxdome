"""FastAPI application for bulk firm payments."""

from collections.abc import Iterator

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from taxdome.db import SessionLocal
from taxdome.payments import PaymentValidationError, process_bulk_payments
from taxdome.schemas import (
    BulkPaymentRequest,
    BulkPaymentResponse,
    ErrorDetail,
    ErrorResponse,
)

app = FastAPI(title="TaxDome Firm Payments", version="1.0.0")
_VALIDATION_MESSAGES = {
    "value_error": "Amount must be a positive decimal string with an exact number of cents",
    "extra_forbidden": "Unexpected field",
    "missing": "Field is missing",
}


def get_session() -> Iterator[Session]:
    """Provide a fresh database session for each request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _field_path(location: tuple[object, ...]) -> str | None:
    parts = [str(part) for part in location if part != "body"]
    return ".".join(parts) or None


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return safe, stable validation errors without echoing submitted values."""
    details = []
    for error in exc.errors():
        error_type = error.get("type", "")
        message = _VALIDATION_MESSAGES.get(error_type, "Invalid request value")
        details.append(
            ErrorDetail(
                code="invalid_request",
                message=message,
                field=_field_path(tuple(error.get("loc", ()))),
            ).model_dump()
        )
    response = ErrorResponse(detail=details)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(mode="json"),
    )


@app.exception_handler(PaymentValidationError)
async def payment_validation_error_handler(
    request: Request, exc: PaymentValidationError
) -> JSONResponse:
    response = ErrorResponse(
        detail=[ErrorDetail(code=exc.code, message=exc.message, field=exc.field)]
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(mode="json"),
    )


@app.post(
    "/api/v1/bulk-payments",
    status_code=status.HTTP_201_CREATED,
    response_model=BulkPaymentResponse,
    responses={status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse}},
)
def create_bulk_payments(
    payload: BulkPaymentRequest, session: Session = Depends(get_session)
) -> BulkPaymentResponse:
    """Create all payments in the request as one database transaction."""
    return process_bulk_payments(session, payload)
