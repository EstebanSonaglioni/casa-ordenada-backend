from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app import tasks
from app.task_models import HouseholdTask
from app.task_schemas import TaskCreate


def test_create_task_scopes_it_to_the_active_household_and_creator(monkeypatch) -> None:
    database = Mock()
    user = SimpleNamespace(id=8)
    monkeypatch.setattr(tasks, "household_for", lambda *_: SimpleNamespace(id=3))
    def refresh(task):
        task.id = 12
        task.status = "pending"

    database.refresh.side_effect = refresh

    result = tasks.create_task(
        TaskCreate(title="Sacar la basura", task_type="cleaning"), user, database
    )

    assert result.id == 12
    added = database.add.call_args.args[0]
    assert added.household_id == 3
    assert added.created_by == 8
    database.commit.assert_called_once()


def test_calendar_rejects_ranges_longer_than_two_months() -> None:
    with pytest.raises(HTTPException) as error:
        tasks.task_calendar(date(2026, 1, 1), date(2026, 4, 1), SimpleNamespace(), Mock())

    assert error.value.status_code == 422


def test_complete_task_creates_an_occurrence_without_closing_habitual_task(monkeypatch) -> None:
    database = Mock()
    user = SimpleNamespace(id=8)
    task = HouseholdTask(
        id=12, household_id=3, title="Barrer", task_type="cleaning", recurrence="daily",
        due_at=datetime(2026, 10, 21, 8), recurrence_days=None, status="pending",
    )
    monkeypatch.setattr(tasks, "household_for", lambda *_: SimpleNamespace(id=3))
    database.scalar.side_effect = [task, None]
    database.refresh.side_effect = lambda occurrence: setattr(occurrence, "id", 20)

    result = tasks.complete_task(12, date(2026, 10, 21), user, database)

    assert result.occurrence_id == 20
    assert result.occurrence_status == "completed"
    assert task.status == "pending"


def test_complete_task_closes_a_one_time_task(monkeypatch) -> None:
    database = Mock()
    user = SimpleNamespace(id=8)
    task = HouseholdTask(
        id=12, household_id=3, title="Sacar basura", task_type="cleaning", recurrence="none",
        due_at=datetime(2026, 10, 21, 8), status="pending",
    )
    monkeypatch.setattr(tasks, "household_for", lambda *_: SimpleNamespace(id=3))
    database.scalar.side_effect = [task, None]
    database.refresh.side_effect = lambda occurrence: setattr(occurrence, "id", 21)

    tasks.complete_task(12, date(2026, 10, 21), user, database)

    assert task.status == "completed"
