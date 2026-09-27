"""Insert the assignment's sample firms without changing existing firms."""

from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from taxdome.db import SessionLocal
from taxdome.models import Firm


SAMPLE_FIRMS: Sequence[dict[str, int | str]] = (
    {
        "name": "Pinecrest CPA Group",
        "balance_cents": 5_000_000,
        "uuid": "3f1c9a2e-7b4d-4c1e-9a55-2d8e6f0b7c41",
    },
    {
        "name": "Lopez Bookkeeping",
        "balance_cents": 50_000,
        "uuid": "8b2e4c71-0d3a-4f6e-b1c9-5a7d2e9f4c10",
    },
    {
        "name": "Nair Tax Services",
        "balance_cents": 200_000,
        "uuid": "e5f18b3c-2a9d-4c07-8e6b-1d4a7f9c3b25",
    },
)


def seed_sample_firms(session: Session) -> int:
    """Add only sample UUIDs that are not already present; return rows added."""
    statement = (
        insert(Firm)
        .values(list(SAMPLE_FIRMS))
        .on_conflict_do_nothing(index_elements=[Firm.uuid])
        .returning(Firm.id)
    )
    result = session.execute(statement)
    return len(result.scalars().all())


def main() -> None:
    with SessionLocal.begin() as session:
        added = seed_sample_firms(session)
    print(f"Inserted {added} sample firm(s). Existing firms were left unchanged.")


if __name__ == "__main__":
    main()
