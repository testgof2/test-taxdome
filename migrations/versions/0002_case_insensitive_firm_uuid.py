"""Make firm UUID uniqueness case-insensitive.

Revision ID: 0002_case_insensitive_uuid
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_case_insensitive_uuid"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_firms_uuid_lower", "firms", [sa.text("lower(uuid)")], unique=True
    )
    op.drop_constraint("uq_firms_uuid", "firms", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_firms_uuid", "firms", ["uuid"])
    op.drop_index("uq_firms_uuid_lower", table_name="firms")
