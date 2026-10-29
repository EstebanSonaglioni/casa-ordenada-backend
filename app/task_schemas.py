from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


TaskType = Literal["cleaning", "cooking", "shopping", "maintenance", "childcare", "pet", "other"]
Difficulty = Literal["easy", "medium", "hard"]
Recurrence = Literal["none", "daily", "weekly", "monthly"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    task_type: TaskType = "other"
    difficulty: Difficulty | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    estimated_amount_cents: int | None = Field(default=None, ge=0)
    currency_id: int | None = Field(default=None, gt=0)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    due_at: datetime | None = None
    recurrence: Recurrence = "none"
    recurrence_days: list[int] | None = None
    recurrence_until: date | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("recurrence_days")
    @classmethod
    def validate_recurrence_days(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("recurrence_days must contain values from 0 to 6")
        return sorted(set(value))

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.recurrence != "none" and self.due_at is None:
            raise ValueError("due_at is required for recurring tasks")
        if self.recurrence == "weekly" and not self.recurrence_days:
            raise ValueError("weekly tasks need at least one recurrence day")
        if self.recurrence == "none" and self.recurrence_days:
            raise ValueError("recurrence_days only applies to recurring tasks")
        if self.recurrence_until and self.due_at and self.recurrence_until < self.due_at.date():
            raise ValueError("recurrence_until must not be before due_at")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    task_type: TaskType | None = None
    difficulty: Difficulty | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    estimated_amount_cents: int | None = Field(default=None, ge=0)
    currency_id: int | None = Field(default=None, gt=0)
    assigned_to_user_id: int | None = Field(default=None, gt=0)
    due_at: datetime | None = None
    recurrence: Recurrence | None = None
    recurrence_days: list[int] | None = None
    recurrence_until: date | None = None
    status: Literal["pending", "cancelled"] | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be blank")
        return cleaned

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("recurrence_days")
    @classmethod
    def validate_recurrence_days(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(day < 0 or day > 6 for day in value):
            raise ValueError("recurrence_days must contain values from 0 to 6")
        return sorted(set(value)) if value is not None else None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    task_type: str
    difficulty: str | None
    duration_minutes: int | None
    estimated_amount_cents: int | None
    currency_id: int | None
    assigned_to_user_id: int | None
    due_at: datetime | None
    recurrence: str
    recurrence_days: list[int]
    recurrence_until: date | None
    status: str
    next_due_at: datetime | None


class TaskOccurrenceResponse(TaskResponse):
    occurrence_id: int | None
    occurrence_date: date
    occurrence_status: str
