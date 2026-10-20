from calendar import monthrange
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.finance_models import (
    AllocationTransfer,
    Category,
    Currency,
    ExchangeRate,
    Expense,
    ExpenseAllocation,
    Household,
    HouseholdMember,
    Income,
    MonthlyAllocation,
    ManualCalendarEvent,
    RecurringDueDateOverride,
    PlannedExpense,
    PlanningPeriod,
    RecurringExpense,
    RecurringPayment,
)
from app.finance_schemas import (
    AllocationCreate,
    AllocationResponse,
    AllocationUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    CalendarEventResponse,
    CalendarPaymentRequest,
    ExpenseCreate,
    ExpenseResponse,
    IncomeCreate,
    IncomeResponse,
    MovementResponse,
    PeriodCreate,
    PeriodResponse,
    PlannedCreate,
    PlannedResponse,
    RecurringCreate,
    SummaryResponse,
    TransferCreate,
    CurrencyResponse,
    ExchangeRateCreate,
    ExchangeRateResponse,
    ManualCalendarEventCreate,
    CalendarMoveRequest,
)
from app.models import User
from app.household_context import active_household_id

router = APIRouter(prefix="/api/v1", tags=["finance"])


def household_for(user: User, database: Session) -> Household:
    query = (
        select(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(HouseholdMember.user_id == user.id)
    )
    selected_id = active_household_id.get()
    if selected_id is not None:
        query = query.where(Household.id == selected_id)
    household = database.scalar(query)
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
    balance = allocation_available_balance(
        allocation.reserved_amount_cents,
        incoming,
        outgoing,
        spent,
    )
    return AllocationResponse(
        id=allocation.id,
        category_id=allocation.category_id,
        currency_id=allocation.currency_id,
        planned_amount_cents=allocation.planned_amount_cents,
        reserved_amount_cents=allocation.reserved_amount_cents,
        spent_amount_cents=spent,
        balance_cents=balance,
    )


def allocation_available_balance(assigned_cents: int, incoming: int, outgoing: int, spent: int) -> int:
    return assigned_cents + incoming - outgoing - spent


def period_response(period: PlanningPeriod) -> PeriodResponse:
    return PeriodResponse(id=period.id, year=period.year, month=period.month, status=period.status)


def currency_for(currency_id: int, database: Session) -> Currency:
    currency = database.get(Currency, currency_id)
    if currency is None or not currency.is_active:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


def latest_rate(base_id: int, quote_id: int, database: Session) -> Decimal:
    if base_id == quote_id:
        return Decimal("1")
    direct = database.scalar(
        select(ExchangeRate).where(
            ExchangeRate.base_currency_id == base_id,
            ExchangeRate.quote_currency_id == quote_id,
        ).order_by(ExchangeRate.effective_at.desc(), ExchangeRate.id.desc())
    )
    if direct is not None:
        return Decimal(str(direct.rate))
    inverse = database.scalar(
        select(ExchangeRate).where(
            ExchangeRate.base_currency_id == quote_id,
            ExchangeRate.quote_currency_id == base_id,
        ).order_by(ExchangeRate.effective_at.desc(), ExchangeRate.id.desc())
    )
    if inverse is None:
        raise HTTPException(status_code=409, detail="No exchange rate available for these currencies")
    return Decimal("1") / Decimal(str(inverse.rate))


def convert_cents(amount_cents: int, base_id: int, quote_id: int, database: Session) -> int:
    converted = Decimal(amount_cents) * latest_rate(base_id, quote_id, database)
    return int(converted.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def movement_sort_key(movement: MovementResponse) -> tuple[date, str]:
    return movement.movement_date, movement.id


def recurring_due_for_month(item: RecurringExpense, year: int, month: int) -> date | None:
    if item.frequency == "yearly" and item.due_date is not None and item.due_date.month != month:
        return None
    day = min(item.due_day, monthrange(year, month)[1])
    return date(year, month, day)


def calendar_status(due_date: date, paid: bool) -> str:
    if paid:
        return "paid"
    today = date.today()
    if due_date < today:
        return "overdue"
    if due_date <= today.fromordinal(today.toordinal() + 3):
        return "due_soon"
    return "pending"


def planned_response(item: PlannedExpense) -> PlannedResponse:
    return PlannedResponse(
        id=item.id,
        category_id=item.category_id,
        currency_id=item.currency_id,
        description=item.description,
        estimated_amount_cents=item.estimated_amount_cents,
        target_date=item.target_date,
        status=item.status,
        notes=item.notes,
        tags=[tag for tag in item.tags.split(",") if tag],
    )


@router.get("/currencies", response_model=list[CurrencyResponse])
def list_currencies(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household_for(user, database)
    return database.scalars(select(Currency).where(Currency.is_active.is_(True)).order_by(Currency.code)).all()


@router.get("/currencies/rates", response_model=list[ExchangeRateResponse])
def list_exchange_rates(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household_for(user, database)
    return database.scalars(select(ExchangeRate).order_by(ExchangeRate.effective_at.desc())).all()


@router.post("/currencies/rates", response_model=ExchangeRateResponse, status_code=201)
def create_exchange_rate(
    data: ExchangeRateCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household_for(user, database)
    currency_for(data.base_currency_id, database)
    currency_for(data.quote_currency_id, database)
    if data.base_currency_id == data.quote_currency_id:
        raise HTTPException(status_code=400, detail="Currencies must be different")
    rate = ExchangeRate(
        base_currency_id=data.base_currency_id,
        quote_currency_id=data.quote_currency_id,
        rate=data.rate,
        effective_at=data.effective_at or datetime.now(timezone.utc),
    )
    database.add(rate)
    database.commit()
    database.refresh(rate)
    return rate


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
    existing = database.scalar(select(Category.id).where(
        Category.household_id == household.id,
        Category.name == data.name,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Ya existe una categoría con ese nombre")
    category = Category(household_id=household.id, **data.model_dump())
    database.add(category)
    database.commit()
    database.refresh(category)
    return CategoryResponse(id=category.id, is_active=category.is_active, **data.model_dump())


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    category = database.scalar(select(Category).where(
        Category.id == category_id,
        Category.household_id == household.id,
    ))
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    category.color = data.color
    database.commit()
    database.refresh(category)
    return CategoryResponse(
        id=category.id,
        name=category.name,
        kind=category.kind,
        color=category.color,
        icon=category.icon,
        is_active=category.is_active,
    )


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


@router.get("/movements", response_model=list[MovementResponse])
def list_movements(
    period_id: int | None = None,
    allocation_id: int | None = None,
    currency_id: int | None = None,
    kind: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 100,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=422, detail="Limit must be between 1 and 200")
    if allocation_id is not None:
        allocation = database.get(MonthlyAllocation, allocation_id)
        if allocation is None or database.get(PlanningPeriod, allocation.planning_period_id).household_id != household.id:
            raise HTTPException(status_code=404, detail="Allocation not found")

    periods = database.scalars(
        select(PlanningPeriod).where(PlanningPeriod.household_id == household.id)
    ).all()
    period_by_id = {period.id: period for period in periods}
    if period_id is not None and period_id not in period_by_id:
        raise HTTPException(status_code=404, detail="Planning period not found")
    period_ids = [period_id] if period_id is not None else list(period_by_id)
    movements: list[MovementResponse] = []

    allocations = database.scalars(
        select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id.in_(period_ids))
    ).all()
    allocation_by_id = {allocation.id: allocation for allocation in allocations}
    for allocation in allocations:
        if allocation_id is not None and allocation.id != allocation_id:
            continue
        period = period_by_id[allocation.planning_period_id]
        movements.append(MovementResponse(
            id=f"allocation-{allocation.id}", kind="allocation", direction="out", movement_date=date(period.year, period.month, 1),
            title="Dinero asignado al sobre", amount_cents=allocation.reserved_amount_cents, currency_id=allocation.currency_id,
            period_id=period.id, allocation_id=allocation.id, category_id=allocation.category_id,
        ))

    incomes = database.scalars(select(Income).where(Income.planning_period_id.in_(period_ids))).all()
    for income in incomes:
        movements.append(MovementResponse(
            id=f"income-{income.id}", kind="income", direction="in", movement_date=income.received_on,
            title=f"{income.source} · {income.received_from}", amount_cents=income.amount_cents, currency_id=income.currency_id,
            period_id=income.planning_period_id,
        ))

    expenses = database.scalars(select(Expense).where(Expense.household_id == household.id, Expense.planning_period_id.in_(period_ids), Expense.status == "posted")).all()
    expense_by_id = {expense.id: expense for expense in expenses}
    expense_allocations = database.scalars(select(ExpenseAllocation).where(ExpenseAllocation.expense_id.in_(expense_by_id))).all()
    for split in expense_allocations:
        allocation = allocation_by_id.get(split.monthly_allocation_id)
        expense = expense_by_id[split.expense_id]
        if allocation is None or (allocation_id is not None and allocation.id != allocation_id):
            continue
        movements.append(MovementResponse(
            id=f"expense-{expense.id}-{split.id}", kind="expense", direction="out", movement_date=expense.expense_date,
            title=expense.description, amount_cents=split.amount_cents, currency_id=expense.currency_id,
            period_id=expense.planning_period_id, allocation_id=allocation.id, category_id=allocation.category_id,
        ))

    transfers = database.scalars(select(AllocationTransfer)).all()
    for transfer in transfers:
        source = allocation_by_id.get(transfer.from_allocation_id)
        target = allocation_by_id.get(transfer.to_allocation_id)
        if source is not None and (allocation_id is None or source.id == allocation_id):
            movements.append(MovementResponse(
                id=f"transfer-{transfer.id}-out", kind="transfer", direction="out", movement_date=transfer.transferred_on,
                title="Transferencia a otro sobre", amount_cents=transfer.amount_cents, currency_id=source.currency_id,
                period_id=source.planning_period_id, allocation_id=source.id, category_id=source.category_id,
            ))
        if target is not None and (allocation_id is None or target.id == allocation_id):
            movements.append(MovementResponse(
                id=f"transfer-{transfer.id}-in", kind="transfer", direction="in", movement_date=transfer.transferred_on,
                title="Transferencia desde otro sobre", amount_cents=transfer.amount_cents, currency_id=target.currency_id,
                period_id=target.planning_period_id, allocation_id=target.id, category_id=target.category_id,
            ))

    if kind is not None:
        movements = [movement for movement in movements if movement.kind == kind]
    if currency_id is not None:
        movements = [movement for movement in movements if movement.currency_id == currency_id]
    if from_date is not None:
        movements = [movement for movement in movements if movement.movement_date >= from_date]
    if to_date is not None:
        movements = [movement for movement in movements if movement.movement_date <= to_date]
    return sorted(movements, key=movement_sort_key, reverse=True)[:limit]


@router.get("/calendar", response_model=list[CalendarEventResponse])
def calendar_events(
    year: int,
    month: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    if month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="Month must be between 1 and 12")
    household = household_for(user, database)
    events: list[CalendarEventResponse] = []
    recurring = database.scalars(
        select(RecurringExpense).where(
            RecurringExpense.household_id == household.id,
            RecurringExpense.active.is_(True),
        )
    ).all()
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    paid_dates = {
        (payment.recurring_expense_id, payment.due_date)
        for payment in database.scalars(
            select(RecurringPayment).where(
                RecurringPayment.due_date >= month_start,
                RecurringPayment.due_date <= month_end,
            )
        )
    }
    for item in recurring:
        override = database.scalar(select(RecurringDueDateOverride).where(
            RecurringDueDateOverride.recurring_expense_id == item.id,
            RecurringDueDateOverride.year == year,
            RecurringDueDateOverride.month == month,
        ))
        due_date = override.due_date if override is not None else recurring_due_for_month(item, year, month)
        if due_date is not None:
            events.append(CalendarEventResponse(
                id=f"recurring-{item.id}-{year}-{month}", kind="recurring", due_date=due_date,
                title=item.name, amount_cents=item.amount_cents, currency_id=item.currency_id,
                category_id=item.category_id, source_id=item.id,
                status=calendar_status(due_date, (item.id, due_date) in paid_dates),
            ))
    planned = database.scalars(
        select(PlannedExpense).where(
            PlannedExpense.household_id == household.id,
            PlannedExpense.status.in_(["planned", "reserved", "paid"]),
            PlannedExpense.target_date >= date(year, month, 1),
            PlannedExpense.target_date <= date(year, month, monthrange(year, month)[1]),
        )
    ).all()
    for item in planned:
        events.append(CalendarEventResponse(
            id=f"planned-{item.id}", kind="planned", due_date=item.target_date,
                title=item.description, amount_cents=item.estimated_amount_cents, currency_id=item.currency_id,
                category_id=item.category_id, source_id=item.id,
                status=calendar_status(item.target_date, item.status == "paid"),
            ))
    manual = database.scalars(select(ManualCalendarEvent).where(
        ManualCalendarEvent.household_id == household.id,
        ManualCalendarEvent.event_date >= month_start,
        ManualCalendarEvent.event_date <= month_end,
    )).all()
    for item in manual:
        events.append(CalendarEventResponse(
            id=f"manual-{item.id}", kind="manual", due_date=item.event_date,
            title=item.title, amount_cents=None, currency_id=None, category_id=None,
            source_id=item.id, status="scheduled", notes=item.notes,
        ))
    return sorted(events, key=lambda item: (item.due_date, item.id))


@router.post("/calendar/events", response_model=CalendarEventResponse, status_code=201)
def create_manual_calendar_event(
    data: ManualCalendarEventCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    event = ManualCalendarEvent(household_id=household.id, created_by=user.id, **data.model_dump())
    database.add(event)
    database.commit()
    database.refresh(event)
    return CalendarEventResponse(
        id=f"manual-{event.id}", kind="manual", due_date=event.event_date,
        title=event.title, amount_cents=None, currency_id=None, category_id=None,
        source_id=event.id, status="scheduled", notes=event.notes,
    )


@router.post("/calendar/recurring/move", response_model=CalendarEventResponse)
def move_recurring_calendar_event(
    data: CalendarMoveRequest,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    item = database.scalar(select(RecurringExpense).where(RecurringExpense.id == data.source_id, RecurringExpense.household_id == household.id))
    if item is None or data.from_date.year != data.to_date.year or data.from_date.month != data.to_date.month:
        raise HTTPException(status_code=400, detail="La nueva fecha debe pertenecer al mismo mes")
    expected = recurring_due_for_month(item, data.from_date.year, data.from_date.month)
    override = database.scalar(select(RecurringDueDateOverride).where(
        RecurringDueDateOverride.recurring_expense_id == item.id,
        RecurringDueDateOverride.year == data.from_date.year,
        RecurringDueDateOverride.month == data.from_date.month,
    ))
    current_date = override.due_date if override is not None else expected
    if current_date != data.from_date:
        raise HTTPException(status_code=409, detail="El vencimiento ya cambió; recargá el calendario")
    if override is None:
        override = RecurringDueDateOverride(recurring_expense_id=item.id, year=data.from_date.year, month=data.from_date.month, due_date=data.to_date)
        database.add(override)
    else:
        override.due_date = data.to_date
    database.commit()
    return CalendarEventResponse(
        id=f"recurring-{item.id}-{data.to_date.year}-{data.to_date.month}", kind="recurring", due_date=data.to_date,
        title=item.name, amount_cents=item.amount_cents, currency_id=item.currency_id, category_id=item.category_id,
        source_id=item.id, status=calendar_status(data.to_date, False),
    )


@router.delete("/calendar/events/{event_id}", status_code=204)
def delete_manual_calendar_event(
    event_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    event = database.scalar(select(ManualCalendarEvent).where(ManualCalendarEvent.id == event_id, ManualCalendarEvent.household_id == household.id))
    if event is None:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    database.delete(event)
    database.commit()


@router.post("/calendar/payments", response_model=CalendarEventResponse)
def set_calendar_payment(
    data: CalendarPaymentRequest,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    if data.kind == "recurring":
        item = database.scalar(select(RecurringExpense).where(
            RecurringExpense.id == data.source_id,
            RecurringExpense.household_id == household.id,
        ))
        override = database.scalar(select(RecurringDueDateOverride).where(
            RecurringDueDateOverride.recurring_expense_id == data.source_id,
            RecurringDueDateOverride.year == data.due_date.year,
            RecurringDueDateOverride.month == data.due_date.month,
        ))
        expected_date = override.due_date if override is not None else (recurring_due_for_month(item, data.due_date.year, data.due_date.month) if item is not None else None)
        if item is None or expected_date != data.due_date:
            raise HTTPException(status_code=404, detail="Recurring payment not found")
        payment = database.scalar(select(RecurringPayment).where(
            RecurringPayment.recurring_expense_id == item.id,
            RecurringPayment.due_date == data.due_date,
        ))
        if data.paid and payment is None:
            database.add(RecurringPayment(recurring_expense_id=item.id, due_date=data.due_date, paid_on=date.today()))
        if not data.paid and payment is not None:
            database.delete(payment)
        database.commit()
        return CalendarEventResponse(
            id=f"recurring-{item.id}-{data.due_date.year}-{data.due_date.month}", kind="recurring", due_date=data.due_date,
            title=item.name, amount_cents=item.amount_cents, currency_id=item.currency_id, category_id=item.category_id,
            source_id=item.id, status=calendar_status(data.due_date, data.paid),
        )
    item = database.scalar(select(PlannedExpense).where(
        PlannedExpense.id == data.source_id,
        PlannedExpense.household_id == household.id,
        PlannedExpense.target_date == data.due_date,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Planned payment not found")
    item.status = "paid" if data.paid else "planned"
    database.commit()
    return CalendarEventResponse(
        id=f"planned-{item.id}", kind="planned", due_date=item.target_date,
        title=item.description, amount_cents=item.estimated_amount_cents, currency_id=item.currency_id, category_id=item.category_id,
        source_id=item.id, status=calendar_status(item.target_date, data.paid),
    )


@router.post("/periods/{period_id}/incomes", response_model=IncomeResponse, status_code=201)
def create_income(
    period_id: int,
    data: IncomeCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    period = period_for(period_id, household.id, database)
    currency_for(data.currency_id, database)
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
    currency_for(data.currency_id, database)
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


@router.patch("/allocations/{allocation_id}", response_model=AllocationResponse)
def update_allocation(
    allocation_id: int,
    data: AllocationUpdate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    allocation = database.get(MonthlyAllocation, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    period = period_for(allocation.planning_period_id, household.id, database)
    if data.planned_amount_cents is not None:
        allocation.planned_amount_cents = data.planned_amount_cents
    if data.reserved_amount_cents is not None:
        allocation.reserved_amount_cents = data.reserved_amount_cents
    database.commit()
    database.refresh(allocation)
    return allocation_response(allocation, database)


@router.delete("/allocations/{allocation_id}", status_code=204)
def delete_allocation(
    allocation_id: int,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    allocation = database.get(MonthlyAllocation, allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    period_for(allocation.planning_period_id, household.id, database)
    has_expenses = database.scalar(select(ExpenseAllocation.id).where(ExpenseAllocation.monthly_allocation_id == allocation.id))
    has_transfers = database.scalar(select(AllocationTransfer.id).where(
        (AllocationTransfer.from_allocation_id == allocation.id) | (AllocationTransfer.to_allocation_id == allocation.id)
    ))
    if has_expenses is not None or has_transfers is not None:
        raise HTTPException(status_code=409, detail="Allocation with movements cannot be deleted")
    database.delete(allocation)
    database.commit()


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
                currency_id=item.currency_id,
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
    currency_for(data.currency_id, database)
    allocations = database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.id.in_(allocation_ids))).all()
    allocation_by_id = {item.id: item for item in allocations}
    if any(allocation_by_id[item.allocation_id].currency_id != data.currency_id for item in data.allocations):
        raise HTTPException(status_code=400, detail="Expense and allocations must use the same currency")
    expense = Expense(
        household_id=household.id,
        planning_period_id=period.id,
        created_by=user.id,
        description=data.description,
        amount_cents=data.amount_cents,
        currency_id=data.currency_id,
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
        currency_id=expense.currency_id,
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
    source = database.get(MonthlyAllocation, data.from_allocation_id)
    target = database.get(MonthlyAllocation, data.to_allocation_id)
    if source.currency_id != target.currency_id:
        raise HTTPException(status_code=400, detail="Transfers must use the same currency")
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
    base_currency_id = 1
    currency_for(base_currency_id, database)
    incomes = database.scalars(select(Income).where(Income.planning_period_id == period.id)).all()
    allocations = database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id)).all()
    allocation_items = [allocation_response(item, database) for item in allocations]
    income = sum(convert_cents(item.amount_cents, item.currency_id, base_currency_id, database) for item in incomes)
    allocated = sum(convert_cents(item.planned_amount_cents, item.currency_id, base_currency_id, database) for item in allocations)
    reserved = sum(convert_cents(item.reserved_amount_cents, item.currency_id, base_currency_id, database) for item in allocations)
    spent = sum(convert_cents(item.spent_amount_cents, allocation.currency_id, base_currency_id, database) for item, allocation in zip(allocation_items, allocations))
    recurring_items = database.scalars(
        select(RecurringExpense).where(
            RecurringExpense.household_id == household.id,
            RecurringExpense.active.is_(True),
            RecurringExpense.frequency == "monthly",
        )
    ).all()
    committed = sum(convert_cents(item.amount_cents, item.currency_id, base_currency_id, database) for item in recurring_items)
    return SummaryResponse(
        period=period_response(period),
        base_currency_id=base_currency_id,
        income_cents=income,
        committed_cents=committed,
        allocated_cents=allocated,
        reserved_future_cents=reserved,
        spent_cents=spent,
        balance_cents=income - reserved,
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
    currency_for(data.currency_id, database)
    values = data.model_dump()
    values["due_day"] = data.due_date.day
    item = RecurringExpense(household_id=household.id, **values)
    database.add(item)
    database.commit()
    database.refresh(item)
    return item


@router.get("/recurring-expenses")
def list_recurring(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(
        select(RecurringExpense).where(RecurringExpense.household_id == household.id).order_by(RecurringExpense.due_date, RecurringExpense.due_day)
    ).all()


@router.post("/planned-expenses", status_code=201)
def create_planned(
    data: PlannedCreate,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    if data.category_id is not None and database.scalar(select(Category.id).where(Category.id == data.category_id, Category.household_id == household.id)) is None:
        raise HTTPException(status_code=404, detail="Category not found")
    currency_for(data.currency_id, database)
    values = data.model_dump(exclude={"tags"})
    values["tags"] = ",".join(data.tags)
    item = PlannedExpense(household_id=household.id, **values)
    database.add(item)
    database.commit()
    database.refresh(item)
    return planned_response(item)


@router.get("/planned-expenses", response_model=list[PlannedResponse])
def list_planned(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    items = database.scalars(
        select(PlannedExpense).where(PlannedExpense.household_id == household.id).order_by(PlannedExpense.target_date)
    ).all()
    return [planned_response(item) for item in items]


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
                    currency_id=allocation.currency_id,
                    reserved_amount_cents=current.balance_cents,
                )
            )
    period.status = "closed"
    database.commit()
    return period_response(next_period)
