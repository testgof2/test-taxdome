# Firm Payments implementation plan

## Scope and decisions

Build a small Python REST service that accepts a bulk payment request from one
firm. If the payer cannot afford the entire batch, reject it with HTTP 422 and
leave the database unchanged. Otherwise, record each payment, debit the payer,
credit recipients, and return HTTP 201 after committing. Correctness must hold
across multiple application instances.

Source: `TA Firm Payments.pdf`, supplied by the user. Document submission
instructions do not authorize publishing the repository or sharing conversations.

Stack: FastAPI, explicitly typed Pydantic DTOs, synchronous SQLAlchemy 2 with
psycopg, PostgreSQL in Docker, Alembic, and pytest. Keep the structure small:
routes, DTOs, database/models, one payment service, and tests.

Work through tasks separately. Use a simpler model for implementation and a
separate agent for review. Address findings, verify the task, and ask the user
to review before proceeding to the next task.

### Request and response contract

Endpoint: `POST /api/v1/bulk-payments`.

| DTO | Explicit fields |
| --- | --- |
| BulkPaymentRequest | payer_firm_uuid: UUID; payments: list[PaymentRequest] |
| PaymentRequest | payee_firm_uuid: UUID; amount: str; description: str |
| BulkPaymentResponse | payer_firm_uuid: UUID; payments: list[PaymentResponse] |
| PaymentResponse | id: int; payee_firm_uuid: UUID; amount: str; description: str |
| ErrorResponse | detail: list[ErrorDetail] |
| ErrorDetail | code: str; message: str; field: str or None |

Dollar amounts arrive as positive strings. Accept more than two decimal places
only when the value is an exact whole number of cents (for example, `1.2300`
becomes 123 cents; `1.235` is rejected). Do not round or truncate. Store and
calculate transfers in integer cents; format response amounts with two decimal
places. A single payment must fit PostgreSQL's positive `INTEGER` cents range.

**User amendment:** accept more than two decimal places only when the amount
still represents an exact number of cents. Reject fractional cents rather than
rounding or truncating them.

Other proposed assumptions from the approved plan:

- Empty payment lists, unknown firms, and self-payments return 422.
- Duplicate recipients are allowed, with one payment record per input entry.
- Amounts must be positive strings; reject numeric JSON values, exponent notation,
  whitespace, non-finite values, fractional cents, and amounts above
  2,147,483,647 cents. Extra decimal places are valid when they are trailing
  zeros that preserve an exact cent value.
- Description is a required string; an empty string is allowed.
- Reject unknown request fields.
- Preserve the specified PostgreSQL INTEGER columns and reject amounts or
  resulting balances outside their range.
- Identical requests represent separate payments. Idempotency is a future improvement.

## Task 1 - Project and database setup

### Test plan

- Verify dependencies install and pytest runs.
- Start PostgreSQL and verify it becomes healthy.
- Verify connectivity through the configured SQLAlchemy engine.
- Verify tests use a separate database from development, with a guard against
  accidentally configuring the development database as the test database.

### Implementation plan

- Add Python project configuration and dependencies.
- Add a Docker Compose PostgreSQL service with a pinned version, health check,
  persistent volume, and a local port that does not conflict with existing containers.
- Add environment configuration and an example environment file.
- Configure SQLAlchemy engine/session creation.
- Establish pytest fixtures and separate development/test databases.
- Document the setup and verification commands needed for this task.

## Task 2 - Database models, migration, and sample data

### Test plan

- Apply the migration to an empty database.
- Verify unique firm UUIDs and valid payment foreign keys.
- Verify database rejection of negative balances and nonpositive payments.
- Verify the three sample firms have the exact supplied UUIDs and balances.
- Verify rerunning the seed command does not duplicate firms or reset existing
  balances, including after a firm's balance has changed.

### Implementation plan

- Define typed SQLAlchemy models for the specified firms and payments tables.
- Preserve the assignment's column names and types.
- Add primary keys, foreign keys, required fields, UUID uniqueness, and monetary
  check constraints.
- Create the initial Alembic migration.
- Add an explicit seed command that inserts missing sample firms and leaves
  existing firms and their balances unchanged.

## Task 3 - DTOs and input validation

### Test plan

- Parametrize valid amounts, including 300, 5800.5, 1200.75, 0.01, and extra
  decimal places that preserve an exact cent value, such as 1.2300.
- Verify exact cent conversion, including rejection of fractional cents such as
  1.235 and 0.001, with no rounding or truncation.
- Cover zero, negative, non-finite, exponent notation, numeric JSON values,
  whitespace, and out-of-range amounts.
- Cover invalid UUIDs, missing fields, nulls, incorrect types, unknown fields,
  and empty payment lists.
- Verify duplicate recipients and preserved descriptions.
- Verify response serialization and consistent error DTOs.

### Implementation plan

- Define all request, response, and error DTOs with explicit types.
- Parse monetary strings with `Decimal` and convert exactly to cents without
  binary floating-point arithmetic, rounding, or truncation.
- Normalize UUIDs for database lookup.
- Enforce structural validation; keep database-dependent checks in the service.

## Task 4 - Atomic payment processing

### Test plan

Run integration tests against PostgreSQL:

- A valid batch creates all payments and updates every balance correctly.
- Spending the exact available balance succeeds.
- Insufficient funds leave balances and payment records unchanged.
- Repeated recipients receive the combined credit, with separate payment rows.
- Unknown firms and self-payments reject the entire batch.
- Recipient balance overflow rejects the entire batch.
- An injected failure after writes begin rolls everything back.
- The total balance across firms remains unchanged.

### Implementation plan

Within one SQLAlchemy transaction:

1. Collect the payer and unique recipient UUIDs.
2. Load and lock all participating firms in a consistent order by firm ID.
3. Verify all firms exist and apply business validation.
4. Calculate the total and check the payer's locked, current balance.
5. Calculate resulting balances and check their ranges.
6. Debit the payer, credit recipients, and insert one record per input payment.
7. Commit once; roll back on failure.

Use PostgreSQL row locks for coordination across application instances.
Acquire locks in consistent order even for opposing transfers.

## Task 5 - REST endpoint and error handling

### Test plan

- Submit the PDF's exact sample request and expect HTTP 201.
- Verify the response DTO and three persisted payment IDs.
- Verify final balances in cents: Pinecrest 3,674,875; Lopez 170,075;
  Nair 1,405,050.
- Verify insufficient funds, malformed input, and other validation failures
  return 422 with the agreed error format and no database changes.
- Verify unexpected persistence failures never return 201 or expose database details.
- Verify OpenAPI documents the request and response schemas.

### Implementation plan

- Add the endpoint and database-session dependency.
- Keep the route thin: validate input, call the service, serialize the result.
- Return 201 only after a successful commit.
- Map input and business validation failures to typed errors.
- Preserve unexpected failures as server errors.

## Task 6 - Concurrency verification

### Test plan

Use separate PostgreSQL connections and application sessions:

- Same payer: two individually affordable requests jointly exceed its balance;
  exactly one succeeds and the other returns 422.
- Shared recipient: simultaneous credits both persist.
- Opposing transfers: A pays B while B pays A; both finish correctly.
- Overlapping batches: different recipient input orders do not create a
  lock-order deadlock.
- Verify payment counts, nonnegative balances, and conservation of money after
  every scenario.

### Implementation plan

- Add concurrency fixtures with committed setup data visible to all connections.
- Coordinate workers with synchronization primitives and bounded timeouts.
- Exercise separate application instances against the same database.
- Use real PostgreSQL because its transaction and lock behavior are central.

## Task 7 - README and final verification

### Test plan

- Follow documented setup from an empty database.
- Run migrations, seed data, start the API, and submit the sample request.
- Run the full pytest suite.
- Verify README examples match the API and actual results.

### Implementation plan

- Document installation, Docker startup, migrations, seeding, startup, and tests.
- Explain transactions, lock ordering, assumptions, limitations, and improvements.
- Preserve meaningful commit history as tasks are implemented.
- Prepare the requested AI usage account and unedited conversation logs for the
  eventual deliverables; do not publish or send them without user authorization.
- Obtain the user's actual time-spent and self-assessment answers for the README.

## Order and scope boundary

Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6 -> Task 7.

Authentication, firm-management endpoints, queues, caching, and idempotency are
outside this initial scope. Task 1 does not include payment models, migrations,
DTOs, payment endpoints, or seed implementation.
