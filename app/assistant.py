import logging
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assistant_models import AssistantCommand
from app.assistant_schemas import AssistantCommandResponse, AssistantConfirmResponse, AssistantProposalUpdate
from app.assistant_service import expiry, interpret, is_supported_audio_type, save_audio, transcribe
from app.auth import get_current_user
from app.database import get_db
from app.finance import household_for
from app.health_models import ExerciseEntry
from app.inventory import active_list
from app.inventory_models import InventoryItem, InventoryMovement, Product, ShoppingItem, StorageLocation
from app.models import User

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])
logger = logging.getLogger(__name__)


def cleanup_expired(database: Session) -> None:
    now = datetime.now(timezone.utc)
    expired = database.scalars(select(AssistantCommand).where(AssistantCommand.expires_at < now, AssistantCommand.status == "awaiting_confirmation")).all()
    for command in expired:
        command.status = "expired"
        if command.audio_path:
            Path(command.audio_path).unlink(missing_ok=True)
            command.audio_path = None
    if expired:
        database.commit()


def command_for(command_id: int, user: User, database: Session) -> AssistantCommand:
    cleanup_expired(database)
    household = household_for(user, database)
    command = database.scalar(select(AssistantCommand).where(AssistantCommand.id == command_id, AssistantCommand.household_id == household.id, AssistantCommand.user_id == user.id))
    if command is None:
        raise HTTPException(status_code=404, detail="Assistant command not found")
    if command.expires_at <= datetime.now(timezone.utc) and command.status == "awaiting_confirmation":
        command.status = "expired"
        database.commit()
        raise HTTPException(status_code=410, detail="Assistant command expired")
    return command


def response(command: AssistantCommand) -> AssistantCommandResponse:
    return AssistantCommandResponse(id=command.id, status=command.status, transcript=command.transcript, proposal=command.proposal, expires_at=command.expires_at)


@router.post("/commands/audio", response_model=AssistantCommandResponse, status_code=201)
async def create_command_from_audio(audio: UploadFile = File(...), user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    cleanup_expired(database)
    if not is_supported_audio_type(audio.content_type):
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    content = await audio.read()
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    try:
        path = save_audio(content, suffix)
        transcript = transcribe(path)
        proposal = interpret(transcript, {"today": date.today().isoformat(), "supported_domains": ["shopping", "exercise", "inventory"], "products": [{"id": item.id, "name": item.name} for item in database.scalars(select(Product).where(Product.household_id == household_for(user, database).id, Product.is_active.is_(True))).all()], "storage_locations": [{"id": item.id, "name": item.name} for item in database.scalars(select(StorageLocation).where(StorageLocation.household_id == household_for(user, database).id)).all()]})
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except Exception as error:
        logger.exception("Voice assistant processing failed")
        raise HTTPException(status_code=502, detail=str(error)) from error
    household = household_for(user, database)
    command = AssistantCommand(household_id=household.id, user_id=user.id, transcript=transcript, proposal=proposal, audio_path=str(path), expires_at=expiry())
    database.add(command)
    database.commit()
    database.refresh(command)
    return response(command)


@router.patch("/commands/{command_id}", response_model=AssistantCommandResponse)
def update_command(command_id: int, data: AssistantProposalUpdate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    command = command_for(command_id, user, database)
    if command.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Assistant command is no longer editable")
    command.proposal = data.proposal
    database.commit()
    database.refresh(command)
    return response(command)


@router.post("/commands/{command_id}/confirm", response_model=AssistantConfirmResponse)
def confirm_command(command_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    command = command_for(command_id, user, database)
    if command.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Assistant command is no longer awaiting confirmation")
    proposal = command.proposal
    data = proposal.get("data", {})
    household = household_for(user, database)
    if proposal.get("missing_fields"):
        raise HTTPException(status_code=422, detail={"message": "The proposal has missing fields", "fields": proposal["missing_fields"]})
    if proposal.get("action") == "shopping.add_item":
        shopping = active_list(household.id, database)
        item = ShoppingItem(shopping_list_id=shopping.id, requested_name=data["requested_name"], quantity_requested=data.get("quantity_requested", 1), quantity_remaining=data.get("quantity_requested", 1), unit=data.get("unit", "unit"), priority=data.get("priority", "normal"), note=data.get("note"))
        database.add(item)
        database.flush()
        result = {"type": "shopping_item", "id": item.id}
    elif proposal.get("action") == "exercise.create":
        entry = ExerciseEntry(household_id=household.id, user_id=user.id, performed_on=data.get("performed_on", date.today().isoformat()), activity=data["activity"], duration_minutes=data["duration_minutes"], notes=data.get("notes"))
        database.add(entry)
        database.flush()
        result = {"type": "exercise_entry", "id": entry.id}
    elif proposal.get("action") == "inventory.add_item":
        required = ["product_id", "storage_location_id", "quantity", "unit", "purchased_on"]
        if any(data.get(field) is None for field in required):
            raise HTTPException(status_code=422, detail={"message": "The inventory proposal has missing fields", "fields": [field for field in required if data.get(field) is None]})
        item = InventoryItem(household_id=household.id, product_id=data["product_id"], storage_location_id=data["storage_location_id"], quantity_initial=data["quantity"], quantity_remaining=data["quantity"], unit=data["unit"], purchased_on=data["purchased_on"], expires_on=data.get("expires_on"))
        database.add(item)
        database.flush()
        database.add(InventoryMovement(inventory_item_id=item.id, type="purchase", quantity=data["quantity"], occurred_on=data["purchased_on"], created_by=user.id))
        result = {"type": "inventory_item", "id": item.id}
    else:
        raise HTTPException(status_code=422, detail="This assistant action is not enabled yet")
    command.status = "confirmed"
    command.confirmed_at = datetime.now(timezone.utc)
    database.commit()
    if command.audio_path:
        Path(command.audio_path).unlink(missing_ok=True)
    return AssistantConfirmResponse(command_id=command.id, status="confirmed", result=result)


@router.post("/commands/{command_id}/cancel", response_model=AssistantCommandResponse)
def cancel_command(command_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    command = command_for(command_id, user, database)
    if command.status != "awaiting_confirmation":
        raise HTTPException(status_code=409, detail="Assistant command is no longer cancellable")
    command.status = "cancelled"
    database.commit()
    return response(command)
