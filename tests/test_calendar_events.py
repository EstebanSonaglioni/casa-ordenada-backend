import pytest
from pydantic import ValidationError

from app.finance_schemas import CalendarMoveRequest, ManualCalendarEventCreate, PlannedCreate


def test_manual_calendar_event_accepts_supported_types_and_trims_title() -> None:
    event = ManualCalendarEventCreate(
        title="  Cobro de sueldo ",
        event_type="salary",
        event_date="2026-10-30",
    )

    assert event.title == "Cobro de sueldo"
    assert event.event_type == "salary"


def test_manual_calendar_event_rejects_unknown_type_or_blank_title() -> None:
    with pytest.raises(ValidationError):
        ManualCalendarEventCreate(title="Cierre", event_type="unknown", event_date="2026-10-30")
    with pytest.raises(ValidationError):
        ManualCalendarEventCreate(title="   ", event_type="other", event_date="2026-10-30")


def test_calendar_move_requires_dates_in_the_request() -> None:
    move = CalendarMoveRequest(source_id=4, from_date="2026-11-01", to_date="2026-11-03")

    assert move.to_date.isoformat() == "2026-11-03"


def test_planned_expense_allows_tags_without_category() -> None:
    planned = PlannedCreate(
        description="Mantenimiento",
        estimated_amount_cents=10000,
        target_date="2026-11-15",
        tags=[" auto ", "#auto", "hogar"],
    )

    assert planned.category_id is None
    assert planned.tags == ["auto", "hogar"]
