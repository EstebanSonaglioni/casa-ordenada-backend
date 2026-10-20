from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.finance import household_for
from app.health_models import ExerciseEntry
from app.health_schemas import (
    ExerciseDayResponse,
    ExerciseEntryCreate,
    ExerciseEntryResponse,
    ExerciseEntryUpdate,
)
from app.models import User

router = APIRouter(prefix="/api/v1/health", tags=["health"])


def entry_for(entry_id: int, household_id: int, user_id: int, database: Session) -> ExerciseEntry:
    entry = database.scalar(select(ExerciseEntry).where(
        ExerciseEntry.id == entry_id,
        ExerciseEntry.household_id == household_id,
        ExerciseEntry.user_id == user_id,
    ))
    if entry is None:
        raise HTTPException(status_code=404, detail="Exercise entry not found")
    return entry


@router.get("/exercise", response_model=list[ExerciseEntryResponse])
def list_exercise(
    from_date: date | None = None,
    to_date: date | None = None,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    household = household_for(user, database)
    statement = select(ExerciseEntry).where(
        ExerciseEntry.household_id == household.id,
        ExerciseEntry.user_id == user.id,
    )
    if from_date:
        statement = statement.where(ExerciseEntry.performed_on >= from_date)
    if to_date:
        statement = statement.where(ExerciseEntry.performed_on <= to_date)
    return database.scalars(statement.order_by(ExerciseEntry.performed_on.desc(), ExerciseEntry.id.desc())).all()


@router.get("/exercise/calendar", response_model=list[ExerciseDayResponse])
def exercise_calendar(
    year: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    if not 2000 <= year <= 2100:
        raise HTTPException(status_code=422, detail="year must be between 2000 and 2100")
    household = household_for(user, database)
    rows = database.execute(
        select(
            ExerciseEntry.performed_on,
            func.count(ExerciseEntry.id),
            func.coalesce(func.sum(ExerciseEntry.duration_minutes), 0),
        ).where(
            ExerciseEntry.household_id == household.id,
            ExerciseEntry.user_id == user.id,
            ExerciseEntry.performed_on >= date(year, 1, 1),
            ExerciseEntry.performed_on <= date(year, 12, 31),
        ).group_by(ExerciseEntry.performed_on).order_by(ExerciseEntry.performed_on)
    ).all()
    return [ExerciseDayResponse(performed_on=row[0], entry_count=row[1], duration_minutes=row[2]) for row in rows]


@router.post("/exercise", response_model=ExerciseEntryResponse, status_code=status.HTTP_201_CREATED)
def create_exercise(data: ExerciseEntryCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    entry = ExerciseEntry(household_id=household.id, user_id=user.id, **data.model_dump())
    database.add(entry)
    database.commit()
    database.refresh(entry)
    return entry


@router.patch("/exercise/{entry_id}", response_model=ExerciseEntryResponse)
def update_exercise(entry_id: int, data: ExerciseEntryUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    entry = entry_for(entry_id, household.id, user.id, database)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    database.commit()
    database.refresh(entry)
    return entry


@router.delete("/exercise/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(entry_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    database.delete(entry_for(entry_id, household.id, user.id, database))
    database.commit()
