"""Create firms and payments tables.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "firms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("balance_cents", sa.Integer(), nullable=False),
        sa.Column("uuid", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "balance_cents >= 0", name="ck_firms_balance_cents_nonnegative"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uuid", name="uq_firms_uuid"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("payer_firm_id", sa.Integer(), nullable=False),
        sa.Column("payee_firm_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "amount_cents > 0", name="ck_payments_amount_cents_positive"
        ),
        sa.ForeignKeyConstraint(["payer_firm_id"], ["firms.id"]),
        sa.ForeignKeyConstraint(["payee_firm_id"], ["firms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("firms")
