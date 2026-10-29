from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.task_schemas import TaskCreate
from app.tasks import occurrence_dates
from app.task_models import HouseholdTask


def test_task_create_trims_text_and_normalizes_weekdays() -> None:
    task = TaskCreate(
        title="  Limpiar cocina  ",
        description="  Después de cenar  ",
        due_at=datetime(2026, 10, 21, 20, 0),
        recurrence="weekly",
        recurrence_days=[3, 1, 3],
    )

    assert task.title == "Limpiar cocina"
    assert task.description == "Después de cenar"
    assert task.recurrence_days == [1, 3]


@pytest.mark.parametrize("value", [-1, 7])
def test_task_create_rejects_invalid_weekday(value: int) -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="Tarea", due_at=datetime(2026, 10, 21), recurrence="weekly", recurrence_days=[value])


def test_recurring_task_requires_schedule() -> None:
    with pytest.raises(ValidationError, match="due_at is required"):
        TaskCreate(title="Tarea", recurrence="daily")


def test_task_create_rejects_negative_amount_and_blank_title() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title=" ", estimated_amount_cents=-1)


def test_daily_occurrences_are_generated_in_requested_range() -> None:
    task = HouseholdTask(
        due_at=datetime(2026, 10, 21, 8, 30), recurrence="daily", recurrence_until=date(2026, 10, 23), recurrence_days=None
    )

    assert list(occurrence_dates(task, date(2026, 10, 20), date(2026, 10, 25))) == [
        date(2026, 10, 21), date(2026, 10, 22), date(2026, 10, 23)
    ]
