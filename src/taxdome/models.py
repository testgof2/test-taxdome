"""SQLAlchemy models for firms and their payments."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from taxdome.db import Base


class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    balance_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    uuid: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("uq_firms_uuid_lower", func.lower(uuid), unique=True),
        CheckConstraint("balance_cents >= 0", name="ck_firms_balance_cents_nonnegative"),
    )


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payments_amount_cents_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payer_firm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("firms.id"), nullable=False
    )
    payee_firm_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("firms.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
