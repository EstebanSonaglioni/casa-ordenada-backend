from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.finance_schemas import ExpenseSplit


class InventoryCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str = Field(default="other", max_length=30)


class InventoryCategoryResponse(InventoryCategoryCreate):
    id: int


class InventoryCategoryUpdate(BaseModel):
    icon: str | None = Field(default=None, max_length=30)
    color: str | None = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")


class InventorySubcategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str = Field(default="other", max_length=30)


class InventorySubcategoryResponse(InventorySubcategoryCreate):
    id: int
    inventory_category_id: int


class StorageLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = Field(default="other", pattern="^(refrigerated|frozen|pantry|bathroom|laundry|other)$")


class StorageLocationResponse(StorageLocationCreate):
    id: int


class ProductCreate(BaseModel):
    inventory_category_id: int
    inventory_subcategory_id: int | None = None
    name: str = Field(min_length=1, max_length=160)
    brand: str = Field(default="", max_length=100)
    default_unit: str = Field(default="unit", max_length=20)


class ProductResponse(ProductCreate):
    id: int
    is_active: bool


class InventoryItemCreate(BaseModel):
    product_id: int
    storage_location_id: int
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="unit", max_length=20)
    purchased_on: date
    expires_on: date | None = None
    notes: str | None = None


class InventoryItemUpdate(BaseModel):
    storage_location_id: int | None = None
    opened: bool | None = None
    open_quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    expires_on: date | None = None
    notes: str | None = None


class InventoryItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    storage_location_id: int
    storage_location_name: str
    quantity_initial: Decimal
    quantity_remaining: Decimal
    unit: str
    purchased_on: date
    expires_on: date | None
    opened_on: date | None
    quantity_opened: Decimal
    status: str
    expiry_status: str


class InventoryQuantityAction(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    occurred_on: date
    note: str | None = None


class InventoryMovementResponse(BaseModel):
    id: int
    type: str
    quantity: Decimal
    occurred_on: date
    note: str | None


class ShoppingItemCreate(BaseModel):
    requested_name: str = Field(min_length=1, max_length=160)
    product_id: int | None = None
    quantity_requested: Decimal = Field(default=Decimal("1"), gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="unit", max_length=20)
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")
    note: str | None = None


class ShoppingItemUpdate(BaseModel):
    quantity_remaining: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    priority: str | None = Field(default=None, pattern="^(low|normal|high)$")
    status: str | None = Field(default=None, pattern="^(pending|purchased|cancelled)$")


class ShoppingItemResponse(ShoppingItemCreate):
    id: int
    status: str
    quantity_remaining: Decimal


class ShoppingListResponse(BaseModel):
    id: int
    name: str
    status: str
    items: list[ShoppingItemResponse]


class CheckoutItem(BaseModel):
    shopping_item_id: int | None = None
    product_id: int | None = None
    exact_name: str = Field(min_length=1, max_length=160)
    inventory_category_id: int | None = None
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(default="unit", max_length=20)
    unit_price_cents: int = Field(ge=0)
    total_price_cents: int = Field(gt=0)
    expires_on: date | None = None
    storage_location_id: int


class CheckoutCreate(BaseModel):
    planning_period_id: int
    currency_id: int
    purchased_on: date
    store: str | None = Field(default=None, max_length=120)
    items: list[CheckoutItem] = Field(min_length=1)
    allocations: list[ExpenseSplit] = Field(min_length=1)

    @model_validator(mode="after")
    def payment_matches_purchase_total(self):
        total = sum(item.total_price_cents for item in self.items)
        if sum(item.amount_cents for item in self.allocations) != total:
            raise ValueError("allocation amounts must equal purchase total")
        return self


class PurchaseResponse(BaseModel):
    id: int
    expense_id: int
    total_amount_cents: int
    currency_id: int
    purchased_on: date
    store: str | None = None


class PurchaseItemResponse(BaseModel):
    exact_name: str
    product_id: int
    quantity: Decimal
    unit: str
    total_price_cents: int
    inventory_category_id: int
    inventory_subcategory_id: int | None


class PurchaseHistoryResponse(PurchaseResponse):
    items: list[PurchaseItemResponse]


class PurchaseUpdate(BaseModel):
    purchased_on: date | None = None
    store: str | None = Field(default=None, max_length=120)
