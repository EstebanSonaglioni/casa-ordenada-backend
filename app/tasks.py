import calendar
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.finance import household_for
from app.finance_models import Currency, HouseholdMember
from app.models import User
from app.task_models import HouseholdTask, HouseholdTaskOccurrence
from app.task_schemas import TaskCreate, TaskOccurrenceResponse, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def task_for(task_id: int, household_id: int, database: Session) -> HouseholdTask:
    task = database.scalar(select(HouseholdTask).where(HouseholdTask.id == task_id, HouseholdTask.household_id == household_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def validate_related(data, household_id: int, database: Session) -> None:
    if data.currency_id is not None:
        currency = database.scalar(select(Currency).where(Currency.id == data.currency_id, Currency.is_active.is_(True)))
        if currency is None:
            raise HTTPException(status_code=422, detail="Currency not found or inactive")
    if data.assigned_to_user_id is not None and database.scalar(select(HouseholdMember.id).where(HouseholdMember.household_id == household_id, HouseholdMember.user_id == data.assigned_to_user_id)) is None:
        raise HTTPException(status_code=422, detail="Assigned user does not belong to this household")


def recurrence_days(task: HouseholdTask) -> list[int]:
    return [int(day) for day in task.recurrence_days.split(",") if day] if task.recurrence_days else []


def occurrence_dates(task: HouseholdTask, start: date, end: date):
    if task.due_at is None or start > end:
        return
    first = max(start, task.due_at.date())
    last = min(end, task.recurrence_until or end)
    if first > last:
        return
    cursor = first
    while cursor <= last:
        matches = task.recurrence == "none" and cursor == task.due_at.date()
        matches = matches or task.recurrence == "daily"
        matches = matches or task.recurrence == "weekly" and cursor.weekday() in recurrence_days(task)
        matches = matches or task.recurrence == "monthly" and cursor.day == min(task.due_at.day, calendar.monthrange(cursor.year, cursor.month)[1])
        if matches:
            yield cursor
        cursor += timedelta(days=1)


def due_at_for(task: HouseholdTask, occurrence_date: date) -> datetime:
    task_time = task.due_at.timetz() if task.due_at else time.min
    return datetime.combine(occurrence_date, task_time).replace(tzinfo=task.due_at.tzinfo if task.due_at else timezone.utc)


def next_due_at(task: HouseholdTask, today: date | None = None) -> datetime | None:
    today = today or datetime.now(timezone.utc).date()
    for occurrence_date in occurrence_dates(task, today, today + timedelta(days=366)):
        occurrence = None
        if occurrence_date >= today:
            return due_at_for(task, occurrence_date)
    return None


def task_response(task: HouseholdTask) -> TaskResponse:
    return TaskResponse(
        id=task.id, title=task.title, description=task.description, task_type=task.task_type,
        difficulty=task.difficulty, duration_minutes=task.duration_minutes,
        estimated_amount_cents=task.estimated_amount_cents, currency_id=task.currency_id,
        assigned_to_user_id=task.assigned_to_user_id, due_at=task.due_at,
        recurrence=task.recurrence, recurrence_days=recurrence_days(task),
        recurrence_until=task.recurrence_until, status=task.status, next_due_at=next_due_at(task),
    )


def validate_task_configuration(task: HouseholdTask) -> None:
    if task.recurrence != "none" and task.due_at is None:
        raise HTTPException(status_code=422, detail="due_at is required for recurring tasks")
    if task.recurrence == "weekly" and not recurrence_days(task):
        raise HTTPException(status_code=422, detail="weekly tasks need at least one recurrence day")
    if task.recurrence == "none":
        task.recurrence_days = None


def occurrence_response(task: HouseholdTask, occurrence_date: date, occurrence: HouseholdTaskOccurrence | None) -> TaskOccurrenceResponse:
    base = task_response(task)
    return TaskOccurrenceResponse(
        **base.model_dump(), occurrence_id=occurrence.id if occurrence else None,
        occurrence_date=occurrence_date,
        occurrence_status=occurrence.status if occurrence else task.status,
    )


@router.get("", response_model=list[TaskResponse])
def list_tasks(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    tasks = database.scalars(select(HouseholdTask).where(HouseholdTask.household_id == household.id, HouseholdTask.status == "pending").order_by(HouseholdTask.due_at, HouseholdTask.title)).all()
    return [task_response(task) for task in tasks]


@router.get("/calendar", response_model=list[TaskOccurrenceResponse])
def task_calendar(from_date: date, to_date: date, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    if from_date > to_date or (to_date - from_date).days > 62:
        raise HTTPException(status_code=422, detail="Invalid calendar date range")
    household = household_for(user, database)
    tasks = database.scalars(select(HouseholdTask).where(HouseholdTask.household_id == household.id, HouseholdTask.status != "cancelled")).all()
    dates = [(task, occurrence_date) for task in tasks for occurrence_date in occurrence_dates(task, from_date, to_date)]
    if not dates:
        return []
    task_ids = [task.id for task, _ in dates]
    occurrences = database.scalars(select(HouseholdTaskOccurrence).where(HouseholdTaskOccurrence.household_id == household.id, HouseholdTaskOccurrence.task_id.in_(task_ids), HouseholdTaskOccurrence.occurrence_date >= from_date, HouseholdTaskOccurrence.occurrence_date <= to_date)).all()
    by_key = {(item.task_id, item.occurrence_date): item for item in occurrences}
    return [occurrence_response(task, occurrence_date, by_key.get((task.id, occurrence_date))) for task, occurrence_date in sorted(dates, key=lambda item: (item[1], item[0].due_at or datetime.min, item[0].title))]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(data: TaskCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    validate_related(data, household.id, database)
    task = HouseholdTask(
        household_id=household.id, created_by=user.id, recurrence_days=",".join(str(day) for day in data.recurrence_days) if data.recurrence_days else None,
        **data.model_dump(exclude={"recurrence_days"}),
    )
    database.add(task)
    database.commit()
    database.refresh(task)
    return task_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, data: TaskUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    task = task_for(task_id, household.id, database)
    validate_related(data, household.id, database)
    values = data.model_dump(exclude_unset=True, exclude={"recurrence_days"})
    if "title" in values and values["title"] is None:
        values.pop("title")
    for field, value in values.items():
        setattr(task, field, value)
    if "recurrence_days" in data.model_fields_set:
        task.recurrence_days = ",".join(str(day) for day in data.recurrence_days) if data.recurrence_days else None
    validate_task_configuration(task)
    database.commit()
    database.refresh(task)
    return task_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    database.delete(task_for(task_id, household.id, database))
    database.commit()


@router.post("/{task_id}/complete/{occurrence_date}", response_model=TaskOccurrenceResponse)
def complete_task(task_id: int, occurrence_date: date, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    task = task_for(task_id, household.id, database)
    if task.status == "cancelled":
        raise HTTPException(status_code=409, detail="Task is cancelled")
    if occurrence_date not in occurrence_dates(task, occurrence_date, occurrence_date):
        raise HTTPException(status_code=422, detail="Date is not scheduled for this task")
    occurrence = database.scalar(select(HouseholdTaskOccurrence).where(HouseholdTaskOccurrence.task_id == task.id, HouseholdTaskOccurrence.occurrence_date == occurrence_date))
    if occurrence is not None and occurrence.status == "completed":
        raise HTTPException(status_code=409, detail="Task occurrence is already completed")
    if occurrence is None:
        occurrence = HouseholdTaskOccurrence(task_id=task.id, household_id=household.id, occurrence_date=occurrence_date)
        database.add(occurrence)
    occurrence.status = "completed"
    occurrence.completed_at = datetime.now(timezone.utc)
    occurrence.completed_by_user_id = user.id
    if task.recurrence == "none":
        task.status = "completed"
    database.commit()
    database.refresh(occurrence)
    return occurrence_response(task, occurrence_date, occurrence)
