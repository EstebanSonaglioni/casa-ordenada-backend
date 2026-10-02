from datetime import date

from pydantic import BaseModel, Field, model_validator


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="variable", pattern="^(fixed|variable|future|other)$")
    color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(default=None, max_length=30)


class CategoryResponse(CategoryCreate):
    id: int
    is_active: bool


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
    received_on: date
    notes: str | None = None


class IncomeResponse(IncomeCreate):
    id: int


class AllocationCreate(BaseModel):
    category_id: int
    planned_amount_cents: int = Field(ge=0)
    reserved_amount_cents: int = Field(default=0, ge=0)


class AllocationResponse(AllocationCreate):
    id: int
    spent_amount_cents: int = 0
    balance_cents: int = 0


class ExpenseSplit(BaseModel):
    allocation_id: int
    amount_cents: int = Field(gt=0)


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    amount_cents: int = Field(gt=0)
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
    expense_date: date
    payment_method: str | None


class RecurringCreate(BaseModel):
    category_id: int
    name: str = Field(min_length=1, max_length=120)
    amount_cents: int = Field(gt=0)
    amount_type: str = Field(default="fixed", pattern="^(fixed|variable)$")
    due_day: int = Field(ge=1, le=31)
    frequency: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    active: bool = True


class PlannedCreate(BaseModel):
    category_id: int
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
    income_cents: int
    committed_cents: int
    allocated_cents: int
    reserved_future_cents: int
    spent_cents: int
    balance_cents: int
    allocations: list[AllocationResponse]
