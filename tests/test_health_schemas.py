from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import health
from app.assistant_service import is_supported_audio_type
from app.health_schemas import ExerciseEntryCreate, ExerciseEntryUpdate


def test_exercise_entry_trims_activity_and_optional_notes() -> None:
    entry = ExerciseEntryCreate(
        performed_on=date(2026, 10, 19), activity="  Caminata  ", duration_minutes=35, notes="  "
    )

    assert entry.activity == "Caminata"
    assert entry.notes is None


@pytest.mark.parametrize("duration", [0, -1, 1441])
def test_exercise_entry_rejects_invalid_duration(duration: int) -> None:
    with pytest.raises(ValidationError):
        ExerciseEntryCreate(performed_on=date.today(), activity="Fuerza", duration_minutes=duration)


def test_exercise_entry_rejects_blank_activity() -> None:
    with pytest.raises(ValidationError, match="activity cannot be blank"):
        ExerciseEntryCreate(performed_on=date.today(), activity="   ", duration_minutes=30)


def test_exercise_update_allows_clearing_notes() -> None:
    update = ExerciseEntryUpdate(notes=None)

    assert update.notes is None


def test_exercise_lookup_rejects_another_users_entry() -> None:
    database = Mock()
    database.scalar.return_value = None

    with pytest.raises(HTTPException) as error:
        health.entry_for(20, household_id=1, user_id=2, database=database)

    assert error.value.status_code == 404


def test_create_exercise_assigns_the_authenticated_user_and_household(monkeypatch) -> None:
    database = Mock()
    user = SimpleNamespace(id=7)
    monkeypatch.setattr(health, "household_for", lambda *_: SimpleNamespace(id=4))

    def refresh(entry) -> None:
        entry.id = 11

    database.refresh.side_effect = refresh
    result = health.create_exercise(
        ExerciseEntryCreate(performed_on=date(2026, 10, 19), activity="Bicicleta", duration_minutes=40),
        user,
        database,
    )

    assert result.id == 11
    assert result.household_id == 4
    assert result.user_id == 7
    database.commit.assert_called_once()


def test_exercise_list_rejects_an_inverted_date_range() -> None:
    with pytest.raises(HTTPException, match="from_date must not be after to_date"):
        health.list_exercise(date(2026, 10, 2), date(2026, 10, 1), SimpleNamespace(), Mock())


def test_audio_mime_type_accepts_codec_parameters() -> None:
    assert is_supported_audio_type("audio/webm;codecs=opus")
    assert not is_supported_audio_type("text/plain")
