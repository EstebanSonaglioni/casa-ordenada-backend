from datetime import date

import pytest
from pydantic import ValidationError

from app.finance import calendar_status, movement_sort_key, recurring_due_for_month
from app.finance_models import RecurringExpense
from app.finance_schemas import ExpenseCreate, MovementResponse, PeriodCreate


def test_expense_splits_must_match_total() -> None:
    with pytest.raises(ValidationError, match="allocation amounts must equal expense amount"):
        ExpenseCreate(
            description="Compra semanal",
            amount_cents=10000,
            expense_date=date(2026, 10, 2),
            allocations=[{"allocation_id": 1, "amount_cents": 9999}],
        )


def test_expense_can_be_split_between_multiple_envelopes() -> None:
    expense = ExpenseCreate(
        description="Compra mixta",
        amount_cents=30000,
        expense_date=date(2026, 10, 2),
        allocations=[
            {"allocation_id": 1, "amount_cents": 18000},
            {"allocation_id": 2, "amount_cents": 12000},
        ],
    )

    assert len(expense.allocations) == 2


def test_period_rejects_invalid_month() -> None:
    with pytest.raises(ValidationError):
        PeriodCreate(year=2026, month=13)


def test_movements_sort_by_date_then_identifier() -> None:
    older = MovementResponse(
        id="income-1", kind="income", direction="in", movement_date=date(2026, 10, 1),
        title="Sueldo", amount_cents=100, currency_id=1, period_id=1,
    )
    newer = MovementResponse(
        id="expense-1", kind="expense", direction="out", movement_date=date(2026, 10, 2),
        title="Compra", amount_cents=100, currency_id=1, period_id=1,
    )

    assert sorted([newer, older], key=movement_sort_key, reverse=True) == [newer, older]


def test_monthly_due_date_clamps_to_last_day_of_month() -> None:
    recurring = RecurringExpense(due_day=31, frequency="monthly")

    assert recurring_due_for_month(recurring, 2026, 2) == date(2026, 2, 28)


def test_yearly_due_date_only_appears_in_its_month() -> None:
    recurring = RecurringExpense(due_day=15, due_date=date(2020, 10, 15), frequency="yearly")

    assert recurring_due_for_month(recurring, 2026, 9) is None
    assert recurring_due_for_month(recurring, 2026, 10) == date(2026, 10, 15)


def test_calendar_status_prioritizes_paid_and_due_states() -> None:
    today = date.today()

    assert calendar_status(today, True) == "paid"
    assert calendar_status(today, False) == "due_soon"
    assert calendar_status(today.fromordinal(today.toordinal() - 1), False) == "overdue"
    assert calendar_status(today.fromordinal(today.toordinal() + 4), False) == "pending"
