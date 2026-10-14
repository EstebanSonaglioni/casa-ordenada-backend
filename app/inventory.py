from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.finance import currency_for, household_for, period_for
from app.finance_models import Expense, ExpenseAllocation, MonthlyAllocation
from app.inventory_models import (
    InventoryCategory,
    InventorySubcategory,
    InventoryItem,
    InventoryMovement,
    Product,
    Purchase,
    PurchaseItem,
    ShoppingItem,
    ShoppingList,
    StorageLocation,
)
from app.inventory_schemas import (
    CheckoutCreate,
    InventoryCategoryCreate,
    InventoryCategoryResponse,
    InventoryCategoryUpdate,
    InventorySubcategoryCreate,
    InventorySubcategoryResponse,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryMovementResponse,
    InventoryQuantityAction,
    ProductCreate,
    ProductResponse,
    PurchaseResponse,
    PurchaseHistoryResponse,
    PurchaseItemResponse,
    PurchaseUpdate,
    ShoppingItemCreate,
    ShoppingItemResponse,
    ShoppingItemUpdate,
    ShoppingListResponse,
    StorageLocationCreate,
    StorageLocationResponse,
)
from app.models import User

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


def category_for(category_id: int, household_id: int, database: Session) -> InventoryCategory:
    category = database.scalar(select(InventoryCategory).where(
        InventoryCategory.id == category_id,
        InventoryCategory.household_id == household_id,
    ))
    if category is None:
        raise HTTPException(status_code=404, detail="Inventory category not found")
    return category


def subcategory_for(subcategory_id: int, category_id: int, database: Session) -> InventorySubcategory:
    item = database.scalar(select(InventorySubcategory).where(
        InventorySubcategory.id == subcategory_id,
        InventorySubcategory.inventory_category_id == category_id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory subcategory not found")
    return item


def location_for(location_id: int, household_id: int, database: Session) -> StorageLocation:
    location = database.scalar(select(StorageLocation).where(
        StorageLocation.id == location_id,
        StorageLocation.household_id == household_id,
    ))
    if location is None:
        raise HTTPException(status_code=404, detail="Storage location not found")
    return location


def product_for(product_id: int, household_id: int, database: Session) -> Product:
    product = database.scalar(select(Product).where(
        Product.id == product_id,
        Product.household_id == household_id,
        Product.is_active.is_(True),
    ))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def expiry_status(item: InventoryItem) -> str:
    if item.status in {"depleted", "discarded"}:
        return item.status
    if item.expires_on is None:
        return "no_expiry"
    today = date.today()
    if item.expires_on < today:
        return "expired"
    if item.expires_on <= today + timedelta(days=3):
        return "due_soon"
    if item.expires_on <= today + timedelta(days=7):
        return "near_expiry"
    return "fresh"


def item_response(item: InventoryItem, products: dict[int, Product], locations: dict[int, StorageLocation]) -> InventoryItemResponse:
    return InventoryItemResponse(
        id=item.id,
        product_id=item.product_id,
        product_name=products[item.product_id].name,
        storage_location_id=item.storage_location_id,
        storage_location_name=locations[item.storage_location_id].name,
        quantity_initial=item.quantity_initial,
        quantity_remaining=item.quantity_remaining,
        unit=item.unit,
        purchased_on=item.purchased_on,
        expires_on=item.expires_on,
        opened_on=item.opened_on,
        quantity_opened=item.quantity_opened,
        status=item.status,
        expiry_status=expiry_status(item),
    )


def active_list(household_id: int, database: Session) -> ShoppingList:
    current = database.scalar(select(ShoppingList).where(
        ShoppingList.household_id == household_id,
        ShoppingList.status == "active",
    ))
    if current is None:
        current = ShoppingList(household_id=household_id)
        database.add(current)
        database.flush()
    return current


def shopping_response(shopping_list: ShoppingList, database: Session) -> ShoppingListResponse:
    items = database.scalars(select(ShoppingItem).where(ShoppingItem.shopping_list_id == shopping_list.id).order_by(ShoppingItem.id)).all()
    return ShoppingListResponse(
        id=shopping_list.id,
        name=shopping_list.name,
        status=shopping_list.status,
        items=[ShoppingItemResponse(
            id=item.id,
            requested_name=item.requested_name,
            product_id=item.product_id,
            quantity_requested=item.quantity_requested,
            quantity_remaining=item.quantity_remaining,
            unit=item.unit,
            priority=item.priority,
            status=item.status,
            note=item.note,
        ) for item in items],
    )


@router.get("/categories", response_model=list[InventoryCategoryResponse])
def list_categories(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(select(InventoryCategory).where(InventoryCategory.household_id == household.id).order_by(InventoryCategory.name)).all()


@router.post("/categories", response_model=InventoryCategoryResponse, status_code=201)
def create_category(data: InventoryCategoryCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category = InventoryCategory(household_id=household.id, **data.model_dump())
    database.add(category)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Inventory category already exists") from error
    database.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=InventoryCategoryResponse)
def update_category(category_id: int, data: InventoryCategoryUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category = category_for(category_id, household.id, database)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(category, field, value)
    database.commit()
    return category


@router.get("/categories/{category_id}/subcategories", response_model=list[InventorySubcategoryResponse])
def list_subcategories(category_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category_for(category_id, household.id, database)
    return database.scalars(select(InventorySubcategory).where(InventorySubcategory.inventory_category_id == category_id).order_by(InventorySubcategory.name)).all()


@router.post("/categories/{category_id}/subcategories", response_model=InventorySubcategoryResponse, status_code=201)
def create_subcategory(category_id: int, data: InventorySubcategoryCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category_for(category_id, household.id, database)
    item = InventorySubcategory(inventory_category_id=category_id, **data.model_dump())
    database.add(item)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Inventory subcategory already exists") from error
    database.refresh(item)
    return item


@router.get("/locations", response_model=list[StorageLocationResponse])
def list_locations(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(select(StorageLocation).where(StorageLocation.household_id == household.id).order_by(StorageLocation.name)).all()


@router.post("/locations", response_model=StorageLocationResponse, status_code=201)
def create_location(data: StorageLocationCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    location = StorageLocation(household_id=household.id, **data.model_dump())
    database.add(location)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Storage location already exists") from error
    database.refresh(location)
    return location


@router.get("/products", response_model=list[ProductResponse])
def list_products(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    return database.scalars(select(Product).where(Product.household_id == household.id, Product.is_active.is_(True)).order_by(Product.name)).all()


@router.post("/products", response_model=ProductResponse, status_code=201)
def create_product(data: ProductCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category_for(data.inventory_category_id, household.id, database)
    if data.inventory_subcategory_id is not None:
        subcategory_for(data.inventory_subcategory_id, data.inventory_category_id, database)
    product = Product(household_id=household.id, **data.model_dump())
    database.add(product)
    try:
        database.commit()
    except Exception as error:
        database.rollback()
        raise HTTPException(status_code=409, detail="Product already exists") from error
    database.refresh(product)
    return product


@router.get("/items", response_model=list[InventoryItemResponse])
def list_items(
    location_id: int | None = None,
    category_id: int | None = None,
    status: str | None = None,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    items = database.scalars(select(InventoryItem).where(InventoryItem.household_id == household.id)).all()
    products = {item.id: item for item in database.scalars(select(Product).where(Product.household_id == household.id))}
    locations = {item.id: item for item in database.scalars(select(StorageLocation).where(StorageLocation.household_id == household.id))}
    filtered = [item for item in items if (location_id is None or item.storage_location_id == location_id) and (category_id is None or products[item.product_id].inventory_category_id == category_id) and (status is None or item.status == status)]
    return [item_response(item, products, locations) for item in filtered]


@router.post("/items", response_model=InventoryItemResponse, status_code=201)
def create_item(data: InventoryItemCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    product = product_for(data.product_id, household.id, database)
    location = location_for(data.storage_location_id, household.id, database)
    item = InventoryItem(household_id=household.id, quantity_initial=data.quantity, quantity_remaining=data.quantity, **data.model_dump(exclude={"quantity"}))
    database.add(item)
    database.flush()
    database.add(InventoryMovement(inventory_item_id=item.id, type="purchase", quantity=data.quantity, occurred_on=data.purchased_on, created_by=user.id))
    database.commit()
    database.refresh(item)
    return item_response(item, {product.id: product}, {location.id: location})


@router.patch("/items/{item_id}", response_model=InventoryItemResponse)
def update_item(item_id: int, data: InventoryItemUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    item = database.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.household_id == household.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if data.storage_location_id is not None:
        location_for(data.storage_location_id, household.id, database)
        item.storage_location_id = data.storage_location_id
    if data.open_quantity is not None:
        if data.open_quantity > item.quantity_remaining:
            raise HTTPException(status_code=409, detail="Open quantity exceeds inventory")
        item.quantity_opened = min(item.quantity_remaining, item.quantity_opened + data.open_quantity)
        item.opened_on = item.opened_on or date.today()
        item.status = "opened"
    if data.opened is True and item.opened_on is None:
        item.quantity_opened = item.quantity_remaining
        item.opened_on = date.today()
        item.status = "opened"
    if data.opened is False:
        item.opened_on = None
        item.quantity_opened = Decimal("0")
        item.status = "closed"
    if data.expires_on is not None:
        item.expires_on = data.expires_on
    if data.notes is not None:
        item.notes = data.notes
    database.commit()
    product = product_for(item.product_id, household.id, database)
    location = location_for(item.storage_location_id, household.id, database)
    return item_response(item, {product.id: product}, {location.id: location})


@router.post("/items/{item_id}/consume", response_model=InventoryItemResponse)
def consume_item(item_id: int, data: InventoryQuantityAction, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    item = database.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.household_id == household.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if data.quantity > item.quantity_remaining:
        raise HTTPException(status_code=409, detail="Quantity exceeds inventory")
    item.quantity_remaining -= data.quantity
    item.quantity_opened = min(item.quantity_opened, item.quantity_remaining)
    if item.quantity_remaining == 0:
        item.status = "depleted"
    database.add(InventoryMovement(inventory_item_id=item.id, type="consume", quantity=data.quantity, occurred_on=data.occurred_on, note=data.note, created_by=user.id))
    database.commit()
    product = product_for(item.product_id, household.id, database)
    location = location_for(item.storage_location_id, household.id, database)
    return item_response(item, {product.id: product}, {location.id: location})


@router.post("/items/{item_id}/discard", response_model=InventoryItemResponse)
def discard_item(item_id: int, data: InventoryQuantityAction, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    item = database.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.household_id == household.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    if data.quantity > item.quantity_remaining:
        raise HTTPException(status_code=409, detail="Quantity exceeds inventory")
    item.quantity_remaining -= data.quantity
    item.quantity_opened = min(item.quantity_opened, item.quantity_remaining)
    if item.quantity_remaining == 0:
        item.status = "discarded"
    database.add(InventoryMovement(inventory_item_id=item.id, type="discard", quantity=data.quantity, occurred_on=data.occurred_on, note=data.note, created_by=user.id))
    database.commit()
    product = product_for(item.product_id, household.id, database)
    location = location_for(item.storage_location_id, household.id, database)
    return item_response(item, {product.id: product}, {location.id: location})


@router.get("/items/{item_id}/movements", response_model=list[InventoryMovementResponse])
def list_item_movements(item_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    item = database.scalar(select(InventoryItem).where(InventoryItem.id == item_id, InventoryItem.household_id == household.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return database.scalars(select(InventoryMovement).where(InventoryMovement.inventory_item_id == item.id).order_by(InventoryMovement.occurred_on.desc(), InventoryMovement.id.desc())).all()


@router.get("/expiring", response_model=list[InventoryItemResponse])
def list_expiring(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    items = database.scalars(select(InventoryItem).where(InventoryItem.household_id == household.id, InventoryItem.status.not_in(["depleted", "discarded"]))).all()
    products = {item.id: item for item in database.scalars(select(Product).where(Product.household_id == household.id))}
    locations = {item.id: item for item in database.scalars(select(StorageLocation).where(StorageLocation.household_id == household.id))}
    return [item_response(item, products, locations) for item in items if expiry_status(item) in {"expired", "due_soon", "near_expiry"}]


@router.get("/shopping-list", response_model=ShoppingListResponse)
def get_shopping_list(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    shopping_list = active_list(household.id, database)
    database.commit()
    return shopping_response(shopping_list, database)


@router.post("/shopping-list/items", response_model=ShoppingItemResponse, status_code=201)
def add_shopping_item(data: ShoppingItemCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    if data.product_id is not None:
        product_for(data.product_id, household.id, database)
    shopping_list = active_list(household.id, database)
    item = ShoppingItem(shopping_list_id=shopping_list.id, quantity_remaining=data.quantity_requested, **data.model_dump())
    database.add(item)
    database.commit()
    database.refresh(item)
    return ShoppingItemResponse(id=item.id, **data.model_dump(), status=item.status, quantity_remaining=item.quantity_remaining)


@router.patch("/shopping-list/items/{item_id}", response_model=ShoppingItemResponse)
def update_shopping_item(item_id: int, data: ShoppingItemUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    item = database.scalar(select(ShoppingItem).join(ShoppingList).where(ShoppingItem.id == item_id, ShoppingList.household_id == household.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Shopping item not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    database.commit()
    return ShoppingItemResponse(id=item.id, requested_name=item.requested_name, product_id=item.product_id, quantity_requested=item.quantity_requested, quantity_remaining=item.quantity_remaining, unit=item.unit, priority=item.priority, status=item.status, note=item.note)


def purchase_response(purchase: Purchase, household_id: int, database: Session) -> PurchaseHistoryResponse:
    lines = database.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id)).all()
    products = {product.id: product for product in database.scalars(select(Product).where(Product.household_id == household_id))}
    return PurchaseHistoryResponse(
        id=purchase.id,
        expense_id=purchase.expense_id,
        total_amount_cents=purchase.total_amount_cents,
        currency_id=purchase.currency_id,
        purchased_on=purchase.purchased_on,
        store=purchase.store,
        items=[PurchaseItemResponse(
            exact_name=line.exact_name,
            product_id=line.product_id,
            quantity=line.quantity,
            unit=line.unit,
            total_price_cents=line.total_price_cents,
            inventory_category_id=products[line.product_id].inventory_category_id,
            inventory_subcategory_id=products[line.product_id].inventory_subcategory_id,
        ) for line in lines],
    )


@router.get("/purchases", response_model=list[PurchaseHistoryResponse])
def list_purchases(
    product_id: int | None = None,
    inventory_category_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
):
    household = household_for(user, database)
    purchases = database.scalars(select(Purchase).where(Purchase.household_id == household.id).order_by(Purchase.purchased_on.desc(), Purchase.id.desc())).all()
    result = []
    for purchase in purchases:
        lines = database.scalars(select(PurchaseItem).where(PurchaseItem.purchase_id == purchase.id)).all()
        product_ids = [line.product_id for line in lines]
        products = {product.id: product for product in database.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_id is not None and product_id not in product_ids:
            continue
        if inventory_category_id is not None and not any(products[line.product_id].inventory_category_id == inventory_category_id for line in lines):
            continue
        if from_date is not None and purchase.purchased_on < from_date:
            continue
        if to_date is not None and purchase.purchased_on > to_date:
            continue
        result.append(purchase_response(purchase, household.id, database))
    return result


@router.patch("/purchases/{purchase_id}", response_model=PurchaseHistoryResponse)
def update_purchase(purchase_id: int, data: PurchaseUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    purchase = database.scalar(select(Purchase).where(Purchase.id == purchase_id, Purchase.household_id == household.id))
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    if data.purchased_on is not None:
        purchase.purchased_on = data.purchased_on
        expense = database.get(Expense, purchase.expense_id)
        if expense is not None:
            expense.expense_date = data.purchased_on
    if data.store is not None:
        purchase.store = data.store
    database.commit()
    return purchase_response(purchase, household.id, database)


@router.post("/checkout", response_model=PurchaseResponse, status_code=201)
def checkout(data: CheckoutCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    period = period_for(data.planning_period_id, household.id, database)
    currency_for(data.currency_id, database)
    allocation_ids = {allocation.id for allocation in database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.planning_period_id == period.id))}
    if any(split.allocation_id not in allocation_ids for split in data.allocations):
        raise HTTPException(status_code=400, detail="All allocations must belong to the period")
    allocations = {allocation.id: allocation for allocation in database.scalars(select(MonthlyAllocation).where(MonthlyAllocation.id.in_(allocation_ids)))}
    if any(allocations[split.allocation_id].currency_id != data.currency_id for split in data.allocations):
        raise HTTPException(status_code=400, detail="Purchase and allocations must use the same currency")
    total = sum(item.total_price_cents for item in data.items)
    expense = Expense(household_id=household.id, planning_period_id=period.id, description="Compra de inventario", amount_cents=total, currency_id=data.currency_id, expense_date=data.purchased_on, created_by=user.id)
    database.add(expense)
    database.flush()
    database.add_all([ExpenseAllocation(expense_id=expense.id, monthly_allocation_id=split.allocation_id, amount_cents=split.amount_cents) for split in data.allocations])
    purchase = Purchase(household_id=household.id, expense_id=expense.id, purchased_on=data.purchased_on, store=data.store, currency_id=data.currency_id, total_amount_cents=total)
    database.add(purchase)
    database.flush()
    default_category = database.scalar(select(InventoryCategory).where(InventoryCategory.household_id == household.id, InventoryCategory.name == "Otros"))
    for line in data.items:
        location_for(line.storage_location_id, household.id, database)
        if line.product_id is not None:
            product = product_for(line.product_id, household.id, database)
        else:
            category = category_for(line.inventory_category_id, household.id, database) if line.inventory_category_id else default_category
            if category is None:
                raise HTTPException(status_code=409, detail="An inventory category is required for this product")
            product = database.scalar(select(Product).where(Product.household_id == household.id, Product.name == line.exact_name, Product.brand == ""))
            if product is None:
                product = Product(household_id=household.id, inventory_category_id=category.id, name=line.exact_name, default_unit=line.unit)
                database.add(product)
                database.flush()
        shopping_item = None
        if line.shopping_item_id is not None:
            shopping_item = database.scalar(select(ShoppingItem).join(ShoppingList).where(ShoppingItem.id == line.shopping_item_id, ShoppingList.household_id == household.id, ShoppingItem.status == "pending"))
            if shopping_item is None:
                raise HTTPException(status_code=404, detail="Shopping item not found")
            shopping_item.quantity_remaining = max(Decimal("0"), shopping_item.quantity_remaining - line.quantity)
            if shopping_item.quantity_remaining == 0:
                shopping_item.status = "purchased"
        purchase_item = PurchaseItem(purchase_id=purchase.id, shopping_item_id=line.shopping_item_id, product_id=product.id, exact_name=line.exact_name, quantity=line.quantity, unit=line.unit, unit_price_cents=line.unit_price_cents, total_price_cents=line.total_price_cents, expires_on=line.expires_on, storage_location_id=line.storage_location_id)
        database.add(purchase_item)
        database.flush()
        inventory_item = InventoryItem(household_id=household.id, product_id=product.id, storage_location_id=line.storage_location_id, purchase_item_id=purchase_item.id, quantity_initial=line.quantity, quantity_remaining=line.quantity, unit=line.unit, purchased_on=data.purchased_on, expires_on=line.expires_on)
        database.add(inventory_item)
        database.flush()
        database.add(InventoryMovement(inventory_item_id=inventory_item.id, type="purchase", quantity=line.quantity, occurred_on=data.purchased_on, created_by=user.id))
    database.commit()
    return PurchaseResponse(id=purchase.id, expense_id=expense.id, total_amount_cents=total, currency_id=purchase.currency_id, purchased_on=purchase.purchased_on, store=purchase.store)
