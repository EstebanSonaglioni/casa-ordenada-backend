from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HouseholdTask(Base):
    __tablename__ = "household_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(40), default="other")
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency_id: Mapped[int | None] = mapped_column(ForeignKey("currencies.id"), nullable=True)
    assigned_to_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    recurrence: Mapped[str] = mapped_column(String(20), default="none", index=True)
    recurrence_days: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recurrence_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HouseholdTaskOccurrence(Base):
    __tablename__ = "household_task_occurrences"
    __table_args__ = (UniqueConstraint("task_id", "occurrence_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("household_tasks.id", ondelete="CASCADE"), index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    occurrence_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
