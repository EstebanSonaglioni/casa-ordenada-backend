from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.inventory import expiry_status
from app.inventory_models import InventoryItem
from app.inventory_schemas import CheckoutCreate, InventoryItemUpdate, ProductCreate, PurchaseUpdate


def test_checkout_rejects_payment_that_does_not_match_items() -> None:
    with pytest.raises(ValidationError, match="allocation amounts must equal purchase total"):
        CheckoutCreate(
            planning_period_id=1,
            currency_id=1,
            purchased_on=date.today(),
            allocations=[{"allocation_id": 1, "amount_cents": 100}],
            items=[{
                "exact_name": "Leche",
                "quantity": "1",
                "total_price_cents": 200,
                "unit_price_cents": 200,
                "storage_location_id": 1,
            }],
        )


def test_inventory_expiry_states_cover_limit_dates() -> None:
    item = InventoryItem(status="closed", expires_on=date.today() + timedelta(days=3))

    assert expiry_status(item) == "due_soon"
    item.expires_on = date.today() - timedelta(days=1)
    assert expiry_status(item) == "expired"
    item.expires_on = None
    assert expiry_status(item) == "no_expiry"
    item.status = "depleted"
    assert expiry_status(item) == "depleted"


def test_product_can_be_created_without_a_subcategory() -> None:
    product = ProductCreate(inventory_category_id=1, name="Agua")

    assert product.inventory_subcategory_id is None


def test_purchase_update_accepts_store_or_date_changes() -> None:
    update = PurchaseUpdate(store="Supermercado", purchased_on=date(2026, 10, 3))

    assert update.store == "Supermercado"


def test_inventory_item_update_accepts_partial_open_quantity() -> None:
    update = InventoryItemUpdate(open_quantity=Decimal("2"))

    assert update.open_quantity == Decimal("2")
