from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50), default="member")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("household_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30), default="variable")
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class PlanningPeriod(Base):
    __tablename__ = "planning_periods"
    __table_args__ = (UniqueConstraint("household_id", "year", "month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")


class Income(Base):
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    planning_period_id: Mapped[int] = mapped_column(ForeignKey("planning_periods.id"), index=True)
    source: Mapped[str] = mapped_column(String(100))
    received_from: Mapped[str] = mapped_column(String(100))
    amount_cents: Mapped[int] = mapped_column(Integer)
    received_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int] = mapped_column(Integer)
    amount_type: Mapped[str] = mapped_column(String(20), default="fixed")
    due_day: Mapped[int] = mapped_column(Integer)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    active: Mapped[bool] = mapped_column(default=True)


class PlannedExpense(Base):
    __tablename__ = "planned_expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(String(160))
    estimated_amount_cents: Mapped[int] = mapped_column(Integer)
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class MonthlyAllocation(Base):
    __tablename__ = "monthly_allocations"
    __table_args__ = (UniqueConstraint("planning_period_id", "category_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    planning_period_id: Mapped[int] = mapped_column(ForeignKey("planning_periods.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    planned_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    reserved_amount_cents: Mapped[int] = mapped_column(Integer, default=0)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    planning_period_id: Mapped[int] = mapped_column(ForeignKey("planning_periods.id"), index=True)
    description: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    expense_date: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="posted")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExpenseAllocation(Base):
    __tablename__ = "expense_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    monthly_allocation_id: Mapped[int] = mapped_column(ForeignKey("monthly_allocations.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)


class AllocationTransfer(Base):
    __tablename__ = "allocation_transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_allocation_id: Mapped[int] = mapped_column(ForeignKey("monthly_allocations.id"))
    to_allocation_id: Mapped[int] = mapped_column(ForeignKey("monthly_allocations.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    transferred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
