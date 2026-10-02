from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="variable", pattern="^(fixed|variable|future|other)$")
    color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(default=None, max_length=30)


class CategoryResponse(CategoryCreate):
    id: int
    is_active: bool


class CurrencyResponse(BaseModel):
    id: int
    code: str
    name: str
    symbol: str
    decimal_places: int
    is_active: bool


class ExchangeRateCreate(BaseModel):
    base_currency_id: int
    quote_currency_id: int
    rate: float = Field(gt=0)
    effective_at: datetime | None = None


class ExchangeRateResponse(ExchangeRateCreate):
    id: int


class PeriodCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class PeriodResponse(PeriodCreate):
    id: int
    status: str


class IncomeCreate(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    received_from: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(gt=0)
    currency_id: int = 1
    received_on: date
    notes: str | None = None


class IncomeResponse(IncomeCreate):
    id: int


class AllocationCreate(BaseModel):
    category_id: int
    currency_id: int = 1
    planned_amount_cents: int = Field(ge=0)
    reserved_amount_cents: int = Field(default=0, ge=0)


class AllocationResponse(AllocationCreate):
    id: int
    spent_amount_cents: int = 0
    balance_cents: int = 0


class AllocationUpdate(BaseModel):
    planned_amount_cents: int | None = Field(default=None, ge=0)
    reserved_amount_cents: int | None = Field(default=None, ge=0)


class ExpenseSplit(BaseModel):
    allocation_id: int
    amount_cents: int = Field(gt=0)


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(gt=0)
    currency_id: int = 1
    expense_date: date
    payment_method: str | None = Field(default=None, max_length=40)
    notes: str | None = None
    allocations: list[ExpenseSplit] = Field(min_length=1)

    @model_validator(mode="after")
    def allocations_match_total(self):
        if sum(item.amount_cents for item in self.allocations) != self.amount_cents:
            raise ValueError("allocation amounts must equal expense amount")
        return self


class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount_cents: int
    currency_id: int
    expense_date: date
    payment_method: str | None


class RecurringCreate(BaseModel):
    category_id: int
    currency_id: int = 1
    name: str = Field(min_length=1, max_length=120)
    amount_cents: int = Field(gt=0)
    amount_type: str = Field(default="fixed", pattern="^(fixed|variable)$")
    due_date: date
    frequency: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    active: bool = True


class PlannedCreate(BaseModel):
    category_id: int
    currency_id: int = 1
    description: str = Field(min_length=1, max_length=160)
    estimated_amount_cents: int = Field(gt=0)
    target_date: date
    notes: str | None = None


class TransferCreate(BaseModel):
    from_allocation_id: int
    to_allocation_id: int
    amount_cents: int = Field(gt=0)
    transferred_on: date
    note: str | None = None


class SummaryResponse(BaseModel):
    period: PeriodResponse
    base_currency_id: int = 1
    income_cents: int
    committed_cents: int
    allocated_cents: int
    reserved_future_cents: int
    spent_cents: int
    balance_cents: int
    allocations: list[AllocationResponse]


class MovementResponse(BaseModel):
    id: str
    kind: str
    direction: str
    movement_date: date
    title: str
    amount_cents: int
    currency_id: int
    period_id: int
    allocation_id: int | None = None
    category_id: int | None = None


class CalendarEventResponse(BaseModel):
    id: str
    kind: str
    due_date: date
    title: str
    amount_cents: int
    currency_id: int
    category_id: int
    source_id: int
    status: str


class CalendarPaymentRequest(BaseModel):
    kind: str = Field(pattern="^(recurring|planned)$")
    source_id: int
    due_date: date
    paid: bool = True
