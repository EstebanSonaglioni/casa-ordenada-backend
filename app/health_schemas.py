from datetime import date

from pydantic import BaseModel, Field, field_validator


class ExerciseEntryCreate(BaseModel):
    performed_on: date
    activity: str = Field(min_length=1, max_length=100)
    duration_minutes: int = Field(gt=0, le=1440)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("activity")
    @classmethod
    def activity_cannot_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("activity cannot be blank")
        return cleaned

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ExerciseEntryUpdate(BaseModel):
    performed_on: date | None = None
    activity: str | None = Field(default=None, min_length=1, max_length=100)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("activity")
    @classmethod
    def update_activity_cannot_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("activity cannot be blank")
        return cleaned


class ExerciseEntryResponse(BaseModel):
    id: int
    performed_on: date
    activity: str
    duration_minutes: int
    notes: str | None


class ExerciseDayResponse(BaseModel):
    performed_on: date
    entry_count: int
    duration_minutes: int
