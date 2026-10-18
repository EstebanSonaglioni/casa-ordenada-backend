from datetime import date, datetime

from pydantic import BaseModel, Field


class ExternalReserveResponse(BaseModel):
    id: int
    external_id: str
    name: str
    amount_cents: int
    currency_id: int
    status: str
    category_id: int | None = None
    updated_at: datetime | None = None


class ExternalMovementResponse(BaseModel):
    id: int
    external_id: str
    movement_type: str
    direction: str
    status: str
    amount_cents: int
    currency_id: int
    description: str
    occurred_at: datetime
    linked_expense_id: int | None = None


class MovementLinkRequest(BaseModel):
    allocation_id: int


class ReserveLinkRequest(BaseModel):
    external_reserve_id: int


class SyncResponse(BaseModel):
    movements_imported: int
    reserves_imported: int
    synced_at: datetime
