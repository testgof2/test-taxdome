# TaxDome API

This repository contains a small FastAPI service for atomic bulk firm payments backed by PostgreSQL. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the staged implementation plan.

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

4. Run the tests:

   ```powershell
   pytest
   ```

   These tests require the Compose database to be healthy. To stop it while keeping data, run `docker compose down`. To reset local data, run `docker compose down -v` and start it again; this permanently deletes the local database volume.

## Database schema and sample data

Apply the Alembic migration explicitly to the database selected by `DATABASE_URL`, then seed the three sample firms:

```powershell
alembic upgrade head
python -m taxdome.seed
```

The application does not run migrations automatically at startup. The seed command inserts a sample firm only when its UUID is missing. Running it again leaves existing firm names and balances unchanged. Keep `DATABASE_URL` pointed at the development database for these commands. Tests use `TEST_DATABASE_URL` and create ORM tables in a temporary schema; pytest does not invoke Alembic or clear the development database. The migration itself is not tested by the test suite.

Balances and payment amounts use integer cents. The database requires unique firm UUIDs, nonnegative firm balances, positive payment amounts, and existing payer and payee firms for every payment.

## API

Start the service after applying the migration and seeding the sample firms:

```powershell
uvicorn taxdome.main:app --reload
```

Submit `POST /api/v1/bulk-payments`. The interactive API docs are available at
`http://127.0.0.1:8000/docs`. A successful batch returns HTTP 201 after the
transaction commits. Validation and business rule failures return HTTP 422 in
the documented `ErrorResponse` format.

## Configuration

`DATABASE_URL` selects the development database. `TEST_DATABASE_URL` selects the separate test database. The SQLAlchemy engine and session factory are available from `taxdome.db`. Configuration is loaded from environment variables and `.env`.
