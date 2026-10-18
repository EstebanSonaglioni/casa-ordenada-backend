import csv
import io
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.finance import currency_for, household_for, period_for
from app.finance_models import Category, Currency, Expense, ExpenseAllocation, MonthlyAllocation
from app.integrations_models import ExternalAccount, ExternalMovement, ExternalReserve, ExternalReserveLink
from app.integrations_schemas import ExternalMovementResponse, ExternalReserveResponse, MovementLinkRequest, ReserveLinkRequest, SyncResponse
from app.models import User

router = APIRouter(prefix="/api/v1/integrations/mercadopago", tags=["mercadopago"])


def account_for(user: User, database: Session) -> ExternalAccount:
    household = household_for(user, database)
    account = database.scalar(select(ExternalAccount).where(ExternalAccount.household_id == household.id, ExternalAccount.provider == "mercadopago"))
    if account is None:
        account = ExternalAccount(household_id=household.id, provider="mercadopago", display_name="Mercado Pago")
        database.add(account)
        database.flush()
    return account


def currency_by_code(code: str, database: Session) -> Currency:
    currency = database.scalar(select(Currency).where(Currency.code == code.upper()))
    if currency is None:
        raise HTTPException(status_code=409, detail=f"Currency {code} is not configured")
    return currency


def response_movement(item: ExternalMovement) -> ExternalMovementResponse:
    return ExternalMovementResponse(id=item.id, external_id=item.external_id, movement_type=item.movement_type, direction=item.direction, status=item.status, amount_cents=item.amount_cents, currency_id=item.currency_id, description=item.description, occurred_at=item.occurred_at, linked_expense_id=item.linked_expense_id)


def response_reserve(item: ExternalReserve, database: Session) -> ExternalReserveResponse:
    link = database.scalar(select(ExternalReserveLink).where(ExternalReserveLink.external_reserve_id == item.id))
    return ExternalReserveResponse(id=item.id, external_id=item.external_id, name=item.name, amount_cents=item.amount_cents, currency_id=item.currency_id, status=item.status, category_id=link.category_id if link else None, updated_at=item.updated_at)


def provider_request(url: str) -> list[dict]:
    if not settings.mercadopago_access_token:
        raise HTTPException(status_code=503, detail="Mercado Pago access token is not configured")
    if not url:
        raise HTTPException(status_code=503, detail="Mercado Pago endpoint is not configured")
    try:
        response = httpx.get(url, headers={"Authorization": f"Bearer {settings.mercadopago_access_token}"}, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Mercado Pago request failed") from error
    if isinstance(payload, list):
        return payload
    return payload.get("results", [])


def account_money_rows() -> list[dict]:
    list_url = settings.mercadopago_movements_url
    if not settings.mercadopago_access_token:
        raise HTTPException(status_code=503, detail="Mercado Pago access token is not configured")
    if not list_url:
        return []
    headers = {"Authorization": f"Bearer {settings.mercadopago_access_token}"}
    try:
        reports_response = httpx.get(list_url, headers=headers, timeout=20)
        reports_response.raise_for_status()
        reports = reports_response.json()
        if not isinstance(reports, list):
            reports = reports.get("results", [])
        rows: list[dict] = []
        base_url = list_url.rsplit("/list", 1)[0]
        for report in reports:
            file_name = report.get("file_name")
            if not file_name:
                continue
            encoded_file_name = quote(file_name, safe="")
            file_response = httpx.get(f"{base_url}/{encoded_file_name}", headers=headers, timeout=30)
            file_response.raise_for_status()
            reader = csv.DictReader(io.StringIO(file_response.text), delimiter=";")
            rows.extend(dict(row) for row in reader)
        return rows
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Mercado Pago account report request failed") from error


@router.get("/movements", response_model=list[ExternalMovementResponse])
def list_external_movements(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    account = account_for(user, database)
    return [response_movement(item) for item in database.scalars(select(ExternalMovement).where(ExternalMovement.account_id == account.id).order_by(ExternalMovement.occurred_at.desc()))]


@router.get("/reserves", response_model=list[ExternalReserveResponse])
def list_external_reserves(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    account = account_for(user, database)
    return [response_reserve(item, database) for item in database.scalars(select(ExternalReserve).where(ExternalReserve.account_id == account.id).order_by(ExternalReserve.name))]


@router.post("/sync", response_model=SyncResponse)
def sync_mercadopago(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    account = account_for(user, database)
    movement_rows = account_money_rows()
    reserve_rows = provider_request(settings.mercadopago_reserves_url)
    currencies = {currency.code: currency for currency in database.scalars(select(Currency))}
    movements_imported = 0
    reserves_imported = 0
    for row in movement_rows:
        external_id = str(row.get("SOURCE_ID") or row.get("EXTERNAL_REFERENCE") or row.get("id") or row.get("payment_id"))
        if not external_id or external_id == "None":
            continue
        currency = currencies.get(str(row.get("TRANSACTION_CURRENCY") or row.get("SETTLEMENT_CURRENCY") or row.get("currency_id", "ARS")).upper())
        if currency is None:
            continue
        amount = Decimal(str(row.get("SETTLEMENT_NET_AMOUNT") or row.get("TRANSACTION_AMOUNT") or row.get("transaction_amount") or row.get("amount", 0)))
        occurred_raw = row.get("TRANSACTION_DATE") or row.get("date_approved") or row.get("date_created")
        if not occurred_raw:
            continue
        values = dict(account_id=account.id, external_id=external_id, movement_type=str(row.get("TRANSACTION_TYPE") or row.get("type", "payment")), direction="out" if amount < 0 else "in", status=str(row.get("status", "approved")), amount_cents=int(abs(amount) * 100), currency_id=currency.id, description=str(row.get("EXTERNAL_REFERENCE") or row.get("description") or row.get("reason") or "Mercado Pago"), occurred_at=datetime.fromisoformat(str(occurred_raw).replace("Z", "+00:00")), raw_data=row)
        item = database.scalar(select(ExternalMovement).where(ExternalMovement.account_id == account.id, ExternalMovement.external_id == external_id))
        if item is None:
            database.add(ExternalMovement(**values)); movements_imported += 1
        else:
            for key, value in values.items(): setattr(item, key, value)
    for row in reserve_rows:
        if row.get("is_reserve") is False:
            continue
        external_id = str(row.get("id") or row.get("external_id"))
        currency = currencies.get(str(row.get("currency_id", "ARS")).upper())
        if not external_id or currency is None:
            continue
        values = dict(account_id=account.id, external_id=external_id, name=str(row.get("name") or f"Reserva MP #{external_id}"), amount_cents=int(Decimal(str(row.get("amount", row.get("available_amount", 0)))) * 100), currency_id=currency.id, status=str(row.get("status", "active")), raw_data=row)
        item = database.scalar(select(ExternalReserve).where(ExternalReserve.account_id == account.id, ExternalReserve.external_id == external_id))
        if item is None:
            database.add(ExternalReserve(**values)); reserves_imported += 1
        else:
            for key, value in values.items(): setattr(item, key, value)
    account.last_synced_at = datetime.now(timezone.utc)
    database.commit()
    return SyncResponse(movements_imported=movements_imported, reserves_imported=reserves_imported, synced_at=account.last_synced_at)


@router.post("/movements/{movement_id}/link", response_model=ExternalMovementResponse)
def link_movement(movement_id: int, data: MovementLinkRequest, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    movement = database.get(ExternalMovement, movement_id)
    account = database.get(ExternalAccount, movement.account_id) if movement else None
    if movement is None or account is None or account.household_id != household.id:
        raise HTTPException(status_code=404, detail="External movement not found")
    if movement.linked_expense_id is not None:
        return response_movement(movement)
    allocation = database.get(MonthlyAllocation, data.allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    period = period_for(allocation.planning_period_id, household.id, database)
    currency_for(movement.currency_id, database)
    if allocation.currency_id != movement.currency_id:
        raise HTTPException(status_code=400, detail="Movement and envelope must use the same currency")
    if movement.direction != "out":
        raise HTTPException(status_code=400, detail="Only outgoing movements can be linked as expenses")
    expense = Expense(household_id=household.id, planning_period_id=period.id, description=movement.description, amount_cents=movement.amount_cents, currency_id=movement.currency_id, expense_date=movement.occurred_at.date(), created_by=user.id)
    database.add(expense); database.flush()
    database.add(ExpenseAllocation(expense_id=expense.id, monthly_allocation_id=allocation.id, amount_cents=movement.amount_cents))
    movement.linked_expense_id = expense.id
    database.commit()
    return response_movement(movement)


@router.post("/categories/{category_id}/reserve", response_model=ExternalReserveResponse)
def link_reserve(category_id: int, data: ReserveLinkRequest, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = household_for(user, database)
    category = database.scalar(select(Category).where(Category.id == category_id, Category.household_id == household.id))
    reserve = database.get(ExternalReserve, data.external_reserve_id)
    account = database.get(ExternalAccount, reserve.account_id) if reserve else None
    if category is None or reserve is None or account is None or account.household_id != household.id:
        raise HTTPException(status_code=404, detail="Category or reserve not found")
    existing = database.scalar(select(ExternalReserveLink).where(ExternalReserveLink.category_id == category.id))
    if existing is None:
        database.add(ExternalReserveLink(household_id=household.id, category_id=category.id, external_reserve_id=reserve.id))
    else:
        existing.external_reserve_id = reserve.id
    database.commit()
    return response_reserve(reserve, database)
