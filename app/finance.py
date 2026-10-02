from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.finance_models import (
    AllocationTransfer,
    Category,
    Expense,
    ExpenseAllocation,
    Household,
    HouseholdMember,
    Income,
    MonthlyAllocation,
    PlannedExpense,
    PlanningPeriod,
    RecurringExpense,
)
from app.finance_schemas import (
    AllocationCreate,
    AllocationResponse,
    CategoryCreate,
    CategoryResponse,
    ExpenseCreate,
    ExpenseResponse,
    IncomeCreate,
    IncomeResponse,
    PeriodCreate,
    PeriodResponse,
    PlannedCreate,
    RecurringCreate,
    SummaryResponse,
    TransferCreate,
)
from app.models import User

router = APIRouter(prefix="/api/v1", tags=["finance"])


def household_for(user: User, database: Session) -> Household:
    household = database.scalar(
        select(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(HouseholdMember.user_id == user.id)
    )
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


def period_for(
    period_id: int,
    household_id: int,
    database: Session,
    require_open: bool = True,
) -> PlanningPeriod:
    period = database.scalar(
        select(PlanningPeriod).where(
            PlanningPeriod.id == period_id,
            PlanningPeriod.household_id == household_id,
        )
    )
    if period is None:
        raise HTTPException(status_code=404, detail="Planning period not found")
    if require_open and period.status != "open":
        raise HTTPException(status_code=409, detail="Planning period is closed")
    return period


def allocation_response(allocation: MonthlyAllocation, database: Session) -> AllocationResponse:
    spent = database.scalar(
        select(func.coalesce(func.sum(ExpenseAllocation.amount_cents), 0))
        .join(Expense, Expense.id == ExpenseAllocation.expense_id)
        .where(
            ExpenseAllocation.monthly_allocation_id == allocation.id,
            Expense.status == "posted",
        )
    ) or 0
    incoming = database.scalar(
        select(func.coalesce(func.sum(AllocationTransfer.amount_cents), 0)).where(
            AllocationTransfer.to_allocation_id == allocation.id
        )
    ) or 0
    outgoing = database.scalar(
        select(func.coalesce(func.sum(AllocationTransfer.amount_cents), 0)).where(
            AllocationTransfer.from_allocation_id == allocation.id
        )
    ) or 0
    balance = allocation.planned_amount_cents + incoming - outgoing - spent
    return AllocationResponse(
        id=allocation.id,
        category_id=allocation.category_id,
        planned_amount_cents=allocation.planned_amount_cents,
        reserved_amount_cents=allocation.reserved_amount_cents,
        spent_amount_cents=spent,
        balance_cents=balance,
    )


def period_response(period: PlanningPeriod) -> PeriodResponse:
    return PeriodResponse(id=period.id, year=period.year, month=period.month, status=period.status)


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return [
        CategoryResponse(
            id=category.id,
            name=category.name,
            kind=category.kind,
            color=category.color,
            icon=category.icon,
            is_active=category.is_active,
        )
        for category in database.scalars(
            select(Category).where(Category.household_id == household.id).order_by(Category.name)
        )
    ]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(
    data: CategoryCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    category = Category(household_id=household.id, **data.model_dump())
    database.add(category)
    database.commit()
    database.refresh(category)
    return CategoryResponse(id=category.id, is_active=category.is_active, **data.model_dump())


@router.post("/periods", response_model=PeriodResponse, status_code=201)
def create_period(
    data: PeriodCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = PlanningPeriod(household_id=household.id, **data.model_dump())
    database.add(period)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Period already exists") from error
    database.refresh(period)
    return period_response(period)


@router.get("/periods", response_model=list[PeriodResponse])
def list_periods(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return [period_response(period) for period in database.scalars(
        select(PlanningPeriod).where(PlanningPeriod.household_id == household.id).order_by(
            PlanningPeriod.year.desc(), PlanningPeriod.month.desc()
        )
    )]


@router.post("/periods/{period_id}/incomes", response_model=IncomeResponse, status_code=201)
def create_income(
    period_id: int,
    data: IncomeCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    income = Income(planning_period_id=period.id, **data.model_dump())
    database.add(income)
    database.commit()
    database.refresh(income)
    return IncomeResponse(id=income.id, **data.model_dump())


@router.post("/periods/{period_id}/allocations", response_model=AllocationResponse, status_code=201)
def create_allocation(
    period_id: int,
    data: AllocationCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    category = database.scalar(select(Category).where(Category.id == data.category_id, Category.household_id == household.id))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    allocation = MonthlyAllocation(planning_period_id=period.id, **data.model_dump())
    database.add(allocation)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Category already allocated for this period") from error
    database.refresh(allocation)
    return allocation_response(allocation, database)


@router.get("/periods/{period_id}/allocations", response_model=list[AllocationResponse])
def list_allocations(
    period_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    allocations = database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id)).all()
    return [allocation_response(item, database) for item in allocations]


@router.post("/periods/{period_id}/generate-recurring", response_model=list[AllocationResponse])
def generate_recurring_allocations(
    period_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    current = {
        allocation.category_id: allocation
        for allocation in database.scalars(
            select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id)
        )
    }
    recurring = database.scalars(
        select(RecurringExpense).where(
            RecurringExpense.household_id == household.id,
            RecurringExpense.active.is_(True),
            RecurringExpense.frequency == "monthly",
        )
    ).all()
    for item in recurring:
        if item.category_id not in current:
            allocation = MonthlyAllocation(
                planning_period_id=period.id,
                category_id=item.category_id,
                planned_amount_cents=item.amount_cents,
            )
            database.add(allocation)
            current[item.category_id] = allocation
    database.commit()
    return [allocation_response(item, database) for item in current.values()]


@router.post("/periods/{period_id}/expenses", response_model=ExpenseResponse, status_code=201)
def create_expense(
    period_id: int,
    data: ExpenseCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    allocation_ids = {item.id for item in database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id))}
    if any(item.allocation_id not in allocation_ids for item in data.allocations):
        raise HTTPException(status_code=400, detail="All allocations must belong to the period")
    expense = Expense(
        household_id=household.id,
        planning_period_id=period.id,
        created_by=user.id,
        description=data.description,
        amount_cents=data.amount_cents,
        expense_date=data.expense_date,
        payment_method=data.payment_method,
        notes=data.notes,
    )
    database.add(expense)
    database.flush()
    database.add_all([
        ExpenseAllocation(expense_id=expense.id, monthly_allocation_id=item.allocation_id, amount_cents=item.amount_cents)
        for item in data.allocations
    ])
    database.commit()
    database.refresh(expense)
    return ExpenseResponse(
        id=expense.id,
        description=expense.description,
        amount_cents=expense.amount_cents,
        expense_date=expense.expense_date,
        payment_method=expense.payment_method,
    )


@router.post("/periods/{period_id}/transfers", status_code=201)
def transfer_allocation(
    period_id: int,
    data: TransferCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    allocation_ids = {item.id for item in database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id))}
    if data.from_allocation_id == data.to_allocation_id or not {data.from_allocation_id, data.to_allocation_id} <= allocation_ids:
        raise HTTPException(status_code=400, detail="Transfer allocations must be different and belong to the period")
    transfer = AllocationTransfer(**data.model_dump())
    database.add(transfer)
    database.commit()
    database.refresh(transfer)
    return {"id": transfer.id, "status": "created"}


@router.get("/periods/{period_id}/summary", response_model=SummaryResponse)
def period_summary(
    period_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database, require_open=False)
    income = database.scalar(select(func.coalesce(func.sum(Income.amount_cents), 0)).where(Income.planning_period_id == period.id)) or 0
    allocations = database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id)).all()
    allocation_items = [allocation_response(item, database) for item in allocations]
    allocated = sum(item.planned_amount_cents for item in allocation_items)
    reserved = sum(item.reserved_amount_cents for item in allocation_items)
    spent = sum(item.spent_amount_cents for item in allocation_items)
    committed = database.scalar(
        select(func.coalesce(func.sum(RecurringExpense.amount_cents), 0)).where(
            RecurringExpense.household_id == household.id,
            RecurringExpense.active.is_(True),
            RecurringExpense.frequency == "monthly",
        )
    ) or 0
    return SummaryResponse(
        period=period_response(period),
        income_cents=income,
        committed_cents=committed,
        allocated_cents=allocated,
        reserved_future_cents=reserved,
        spent_cents=spent,
        balance_cents=income - allocated - reserved,
        allocations=allocation_items,
    )


@router.post("/recurring-expenses", status_code=201)
def create_recurring(
    data: RecurringCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    category = database.scalar(select(Category).where(Category.id == data.category_id, Category.household_id == household.id))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    item = RecurringExpense(household_id=household.id, **data.model_dump())
    database.add(item)
    database.commit()
    database.refresh(item)
    return item


@router.get("/recurring-expenses")
def list_recurring(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(
        select(RecurringExpense).where(RecurringExpense.household_id == household.id).order_by(RecurringExpense.due_day)
    ).all()


@router.post("/planned-expenses", status_code=201)
def create_planned(
    data: PlannedCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    category = database.scalar(select(Category).where(Category.id == data.category_id, Category.household_id == household.id))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    item = PlannedExpense(household_id=household.id, **data.model_dump())
    database.add(item)
    database.commit()
    database.refresh(item)
    return item


@router.get("/planned-expenses")
def list_planned(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(
        select(PlannedExpense).where(PlannedExpense.household_id == household.id).order_by(PlannedExpense.target_date)
    ).all()


@router.post("/periods/{period_id}/rollover", response_model=PeriodResponse, status_code=201)
def rollover_period(
    period_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    next_year, next_month = (period.year + 1, 1) if period.month == 12 else (period.year, period.month + 1)
    existing_next = database.scalar(
        select(PlanningPeriod).where(
            PlanningPeriod.household_id == household.id,
            PlanningPeriod.year == next_year,
            PlanningPeriod.month == next_month,
        )
    )
    if existing_next is not None:
        raise HTTPException(status_code=409, detail="Next period already exists")
    current_allocations = database.scalars(
        select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id)
    ).all()
    next_period = PlanningPeriod(household_id=household.id, year=next_year, month=next_month)
    database.add(next_period)
    database.flush()
    for allocation in current_allocations:
        current = allocation_response(allocation, database)
        if current.balance_cents > 0:
            database.add(
                MonthlyAllocation(
                    planning_period_id=next_period.id,
                    category_id=allocation.category_id,
                    planned_amount_cents=current.balance_cents,
                )
            )
    period.status = "closed"
    database.commit()
    return period_response(next_period)
