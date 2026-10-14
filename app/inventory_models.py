from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryCategory(Base):
    __tablename__ = "inventory_categories"
    __table_args__ = (UniqueConstraint("household_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    icon: Mapped[str] = mapped_column(String(30), default="other")


class InventorySubcategory(Base):
    __tablename__ = "inventory_subcategories"
    __table_args__ = (UniqueConstraint("inventory_category_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_category_id: Mapped[int] = mapped_column(ForeignKey("inventory_categories.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(30), default="other")


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    __table_args__ = (UniqueConstraint("household_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30), default="other")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("household_id", "name", "brand"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    inventory_category_id: Mapped[int] = mapped_column(ForeignKey("inventory_categories.id"))
    inventory_subcategory_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_subcategories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    brand: Mapped[str] = mapped_column(String(100), default="")
    default_unit: Mapped[str] = mapped_column(String(20), default="unit")
    is_active: Mapped[bool] = mapped_column(default=True)


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Compras pendientes")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(ForeignKey("shopping_lists.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    requested_name: Mapped[str] = mapped_column(String(160))
    quantity_requested: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit: Mapped[str] = mapped_column(String(20), default="unit")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    shopping_list_id: Mapped[int | None] = mapped_column(ForeignKey("shopping_lists.id"), nullable=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), unique=True)
    purchased_on: Mapped[date] = mapped_column(Date)
    store: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"))
    total_amount_cents: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    shopping_item_id: Mapped[int | None] = mapped_column(ForeignKey("shopping_items.id"), nullable=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    exact_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))
    unit_price_cents: Mapped[int] = mapped_column(Integer)
    total_price_cents: Mapped[int] = mapped_column(Integer)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_location_id: Mapped[int] = mapped_column(ForeignKey("storage_locations.id"))


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    storage_location_id: Mapped[int] = mapped_column(ForeignKey("storage_locations.id"))
    purchase_item_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_items.id"), nullable=True)
    quantity_initial: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    quantity_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit: Mapped[str] = mapped_column(String(20))
    purchased_on: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    opened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    quantity_opened: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    status: Mapped[str] = mapped_column(String(20), default="closed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    occurred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
