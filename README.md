# Firm Payments API

A small FastAPI service that transfers a firm's balance to several other firms in one request. It validates the whole batch before writing: a successful request records every payment, updates the balances, and returns `201`; an unaffordable batch returns `422` and changes nothing.

## Run locally

Use Python 3.12 or 3.13 and Docker. From the repository root, run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d --wait db
alembic upgrade head
python -m taxdome.seed
uvicorn taxdome.main:app --reload
```

The API runs at `http://127.0.0.1:8000`; interactive schemas are at `/docs`. PostgreSQL is exposed only at `127.0.0.1:55432`. The Compose volume retains local data. Run migrations explicitly after schema changes; neither app startup nor pytest runs Alembic. Seeding again inserts only missing sample firms and leaves existing balances alone.

`DATABASE_URL` selects the application database. `TEST_DATABASE_URL` must select a different database; `.env.example` supplies local defaults. The Compose initialization creates both databases on a new volume. If the volume already existed before the test database was added, create `taxdome_test` manually or use a fresh local volume.

## Try the sample payment

The seed command creates the three firms from the assignment. With a fresh database and the API running, submit:

```powershell
$body = @'
{
  "payer_firm_uuid": "3f1c9a2e-7b4d-4c1e-9a55-2d8e6f0b7c41",
  "payments": [
    {"amount": "6250", "payee_firm_uuid": "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25", "description": "Overflow returns, August 2026"},
    {"amount": "5800.5", "payee_firm_uuid": "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25", "description": "Amended returns, August 2026"},
    {"amount": "1200.75", "payee_firm_uuid": "8b2e4c71-0d3a-4f6e-b1c9-5a7d2e9f4c10", "description": "Bookkeeping cleanup, 3 clients"}
  ]
}
'@
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/bulk-payments -ContentType application/json -Body $body
```

The response is `201 Created` with the payer UUID and three payment objects. Each object contains a generated integer `id`, the payee UUID, its description, and a two-decimal amount (`6250.00`, `5800.50`, or `1200.75`). On a fresh database, the resulting balances are Pinecrest `$36,748.75`, Lopez `$1,700.75`, and Nair `$14,050.50`. Sending the request again makes another payment batch, so use a fresh database when checking those balances.

Run the test suite with `pytest`. It uses PostgreSQL and creates temporary tables in isolated schemas in `taxdome_test`; it does not modify the development database. The focused tests cover exact cent parsing, atomic transfers and rollback, the HTTP contract, and concurrent requests. To stop PostgreSQL without deleting data, run `docker compose down`. `docker compose down -v` permanently removes the local volume.

## Design and review notes

- SQLAlchemy stores amounts and balances as integer cents. Request amounts must be positive decimal **strings** that represent exact cents. Extra trailing zeros are allowed (`"1.2300"`); fractional cents are rejected (`"1.235"`). The service never rounds money.
- One SQLAlchemy transaction locks every participating firm in ascending database ID order. It checks the payer's current balance, validates recipients and integer ranges, then writes all balances and payment rows together. The database locks coordinate requests across server instances and avoid opposing-transfer deadlocks.
- Duplicate recipients are allowed and receive a combined credit, with one payment row per request entry. Empty batches, unknown firms, self-payments, invalid amounts, and insufficient funds return `422` with a typed `detail` list containing `code`, `message`, and `field`.
- Concurrency tests needed reliable overlap: each worker uses its own PostgreSQL connection and waits behind a held row lock before both requests proceed. Test data lives in isolated schemas in the separate test database.
- The assignment's sample payload uses multiple payments to Nair. This is why the service sums recipient credits but still records each payment separately.
- This version has no authentication or idempotency key. Identical submissions create separate payments. For a production service, add authorization and an idempotency key so clients can safely retry after a lost response.

The implementation was developed with Codex for planning, coding, test review, and documentation. The required unedited conversation log should be supplied separately with the eventual submission; it is not included in this repository. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the staged plan and the repository history for the implementation sequence.

## Assignment questions

- Time spent: **3 hours.**
- Pride in the work: **Good enough.**
