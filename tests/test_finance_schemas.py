from datetime import date

import pytest
from pydantic import ValidationError

from app.finance_schemas import ExpenseCreate, PeriodCreate


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
