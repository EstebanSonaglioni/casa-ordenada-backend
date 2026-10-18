from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExternalAccount(Base):
    __tablename__ = "external_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    external_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    display_name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalReserve(Base):
    __tablename__ = "external_reserves"
    __table_args__ = (UniqueConstraint("account_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("external_accounts.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"))
    status: Mapped[str] = mapped_column(String(30), default="active")
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ExternalReserveLink(Base):
    __tablename__ = "external_reserve_links"
    __table_args__ = (UniqueConstraint("category_id"), UniqueConstraint("external_reserve_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    external_reserve_id: Mapped[int] = mapped_column(ForeignKey("external_reserves.id"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalMovement(Base):
    __tablename__ = "external_movements"
    __table_args__ = (UniqueConstraint("account_id", "external_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("external_accounts.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(160))
    movement_type: Mapped[str] = mapped_column(String(40), default="payment")
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"))
    description: Mapped[str] = mapped_column(String(240))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    linked_expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
