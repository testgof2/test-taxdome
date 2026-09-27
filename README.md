# Firm Payments API

One request pays several firms. The service checks that the payer can afford the full batch, then records every payment and updates the balances in one transaction. If the payer cannot cover it, the API returns `422` and changes nothing.

## Run locally

With Python 3.12 or 3.13 and Docker, run:

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

The API runs at `http://127.0.0.1:8000`, with interactive docs at `/docs`. `.env.example` sets separate development and test database URLs. Run migrations explicitly; startup and pytest never run Alembic. The seed command is safe to repeat: it leaves existing firms and balances alone. On an older Compose volume, you may need to create `taxdome_test` yourself.

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

The response is `201 Created` with three payment IDs. On a fresh database, Pinecrest finishes with `$36,748.75`, Lopez with `$1,700.75`, and Nair with `$14,050.50`. Each submission creates a new batch, so start fresh when checking those balances.

Run `pytest` to check the API, balances, rollback, and concurrent transfers. Tests use `taxdome_test`, never the development database. The end-to-end test creates a temporary database, so the test role needs `CREATEDB`. `docker compose down` stops PostgreSQL without deleting its data.

## Approach and trade-offs

Amounts are positive decimal strings stored as integer cents. `"1.2300"` is valid; `"1.235"` is rejected rather than rounded. The service locks participating firms in ID order and commits the whole batch at once. Repeated recipients get a combined credit but still have separate payment records. Invalid requests and business-rule failures return a typed `422` response.

Concurrency was the main tricky part. The tests force requests to overlap on real PostgreSQL row locks. UUIDs are stored as text, so lookup and uniqueness are case-insensitive; any existing firms whose UUIDs differ only by case need to be reconciled before migration `0002`.

## What I would improve next

- Add an idempotency key so a client can safely retry after losing a response. Today, a retry pays again.
- Check that the caller is allowed to spend from the payer firm.
- Limit batch size so one request cannot hold firm locks for too long.
- If every firm writer guarantees canonical UUIDs, simplify the case-insensitive UUID handling.

I used Codex for planning, coding, review, and documentation. The [Word dialogue export](AI_DIALOGUE.docx) contains the unedited user-visible messages; refresh it if this conversation continues. The commit history shows the implementation sequence.

## Assignment questions

- Time spent: **3 hours.**
- Pride in the work: **Good enough.**
