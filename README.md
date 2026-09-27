# TaxDome API

This repository contains the database foundation for a small FastAPI service backed by PostgreSQL. The payment endpoint is planned for a later task. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Local setup

1. Create a virtual environment and install the pinned dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   ```

   The project supports Python 3.12 and 3.13.

2. Copy `.env.example` to `.env`. The sample values are for local development only.

3. Start PostgreSQL:

   ```powershell
   docker compose up -d --wait db
   docker compose ps
   ```

   PostgreSQL is published only on `127.0.0.1:55432`. Compose keeps its data in the `postgres_data` volume. The container initializes both `taxdome` and `taxdome_test` databases the first time the volume is created.

4. Run the database smoke tests:

   ```powershell
   pytest
   ```

   These tests require the Compose database to be healthy. To stop it while keeping data, run `docker compose down`. To reset local data, run `docker compose down -v` and start it again; this permanently deletes the local database volume.

## Database schema and sample data

Apply the Alembic migration to the database selected by `DATABASE_URL`, then seed the three sample firms:

```powershell
alembic upgrade head
python -m taxdome.seed
```

The seed command inserts a sample firm only when its UUID is missing. Running it again leaves existing firm names and balances unchanged. Keep `DATABASE_URL` pointed at the development database for these commands. Tests use `TEST_DATABASE_URL` and a temporary schema, and do not migrate or clear the development database.

Balances and payment amounts use integer cents. The database requires unique firm UUIDs, nonnegative firm balances, positive payment amounts, and existing payer and payee firms for every payment.

## Configuration

`DATABASE_URL` selects the development database. `TEST_DATABASE_URL` selects the separate test database. The SQLAlchemy engine and session factory are available from `taxdome.db`. Configuration is loaded from environment variables and `.env`.
