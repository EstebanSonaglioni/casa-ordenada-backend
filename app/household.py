from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.finance_models import Household, HouseholdInvitation, HouseholdMember
from app.household_schemas import (
    HouseholdCreate,
    HouseholdResponse,
    InvitationCreate,
    InvitationResponse,
    MemberResponse,
)
from app.models import User
from app.security import decode_token

router = APIRouter(prefix="/api/v1", tags=["households"])


class NotificationManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        connections = self.connections.get(user_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self.connections.pop(user_id, None)

    async def notify(self, user_id: int, event: dict) -> None:
        for websocket in list(self.connections.get(user_id, set())):
            try:
                await websocket.send_json(event)
            except Exception:
                self.disconnect(user_id, websocket)


notification_manager = NotificationManager()


def membership_for(household_id: int, user_id: int, database: Session) -> HouseholdMember:
    membership = database.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="No perteneces a esta casa")
    return membership


def invitation_response(invitation: HouseholdInvitation, database: Session) -> InvitationResponse:
    household = database.get(Household, invitation.household_id)
    invited = database.get(User, invitation.invited_user_id)
    inviter = database.get(User, invitation.invited_by_user_id)
    return InvitationResponse(
        id=invitation.id,
        household_id=invitation.household_id,
        household_name=household.name if household else "",
        invited_username=invited.username if invited else "",
        invited_by_username=inviter.username if inviter else "",
        role=invitation.role,
        status=invitation.status,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        responded_at=invitation.responded_at,
    )


@router.post("/households", response_model=HouseholdResponse, status_code=201)
def create_household(data: HouseholdCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    household = Household(name=data.name.strip())
    database.add(household)
    database.flush()
    database.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    database.commit()
    return HouseholdResponse(id=household.id, name=household.name, role="owner")


@router.get("/households", response_model=list[HouseholdResponse])
def list_households(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    rows = database.execute(
        select(Household, HouseholdMember.role)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(HouseholdMember.user_id == user.id)
        .order_by(Household.name)
    ).all()
    return [HouseholdResponse(id=household.id, name=household.name, role=role) for household, role in rows]


@router.get("/households/{household_id}/members", response_model=list[MemberResponse])
def list_members(household_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    membership_for(household_id, user.id, database)
    rows = database.execute(
        select(User, HouseholdMember.role)
        .join(HouseholdMember, HouseholdMember.user_id == User.id)
        .where(HouseholdMember.household_id == household_id)
        .order_by(User.display_name, User.username)
    ).all()
    return [MemberResponse(user_id=item.id, username=item.username, display_name=item.display_name, role=role) for item, role in rows]


@router.post("/households/{household_id}/invitations", response_model=InvitationResponse, status_code=201)
async def invite_user(household_id: int, data: InvitationCreate, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    membership = membership_for(household_id, user.id, database)
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Solo el owner puede invitar usuarios")
    invited = database.scalar(select(User).where(User.username == data.username.strip()))
    if invited is None:
        raise HTTPException(status_code=404, detail="No existe un usuario con ese nombre")
    if invited.id == user.id:
        raise HTTPException(status_code=400, detail="No podés invitarte a vos mismo")
    if database.scalar(select(HouseholdMember.id).where(HouseholdMember.household_id == household_id, HouseholdMember.user_id == invited.id)):
        raise HTTPException(status_code=409, detail="El usuario ya pertenece a esta casa")
    pending = database.scalar(select(HouseholdInvitation).where(HouseholdInvitation.household_id == household_id, HouseholdInvitation.invited_user_id == invited.id, HouseholdInvitation.status == "pending"))
    if pending is not None:
        raise HTTPException(status_code=409, detail="Ya existe una invitación pendiente")
    invitation = HouseholdInvitation(
        household_id=household_id,
        invited_user_id=invited.id,
        invited_by_user_id=user.id,
        role=data.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    database.add(invitation)
    database.commit()
    database.refresh(invitation)
    response = invitation_response(invitation, database)
    await notification_manager.notify(invited.id, {"type": "invitation.created", "invitation_id": invitation.id})
    return response


@router.get("/invitations", response_model=list[InvitationResponse])
def list_pending_invitations(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    invitations = database.scalars(select(HouseholdInvitation).where(HouseholdInvitation.invited_user_id == user.id).order_by(HouseholdInvitation.created_at.desc())).all()
    changed = False
    for invitation in invitations:
        if invitation.status == "pending" and invitation.expires_at <= now:
            invitation.status = "expired"
            changed = True
    if changed:
        database.commit()
    return [invitation_response(item, database) for item in invitations if item.status == "pending"]


@router.get("/invitations/history", response_model=list[InvitationResponse])
def invitation_history(user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    invitations = database.scalars(select(HouseholdInvitation).where(HouseholdInvitation.invited_user_id == user.id).order_by(HouseholdInvitation.created_at.desc())).all()
    return [invitation_response(item, database) for item in invitations]


def respond_to_invitation(invitation_id: int, response_status: str, user: User, database: Session) -> InvitationResponse:
    invitation = database.scalar(select(HouseholdInvitation).where(HouseholdInvitation.id == invitation_id, HouseholdInvitation.invited_user_id == user.id))
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    if invitation.status != "pending":
        raise HTTPException(status_code=409, detail="La invitación ya fue respondida")
    if invitation.expires_at <= datetime.now(timezone.utc):
        invitation.status = "expired"
        database.commit()
        raise HTTPException(status_code=409, detail="La invitación expiró")
    invitation.status = response_status
    invitation.responded_at = datetime.now(timezone.utc)
    if response_status == "accepted":
        database.add(HouseholdMember(household_id=invitation.household_id, user_id=user.id, role=invitation.role))
    database.commit()
    database.refresh(invitation)
    return invitation_response(invitation, database)


@router.post("/invitations/{invitation_id}/accept", response_model=InvitationResponse)
def accept_invitation(invitation_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    return respond_to_invitation(invitation_id, "accepted", user, database)


@router.post("/invitations/{invitation_id}/reject", response_model=InvitationResponse)
def reject_invitation(invitation_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    return respond_to_invitation(invitation_id, "rejected", user, database)


@router.delete("/households/{household_id}/invitations/{invitation_id}", response_model=InvitationResponse)
def cancel_invitation(household_id: int, invitation_id: int, user: User = Depends(get_current_user), database: Session = Depends(get_db)):
    membership = membership_for(household_id, user.id, database)
    if membership.role != "owner":
        raise HTTPException(status_code=403, detail="Solo el owner puede cancelar invitaciones")
    invitation = database.scalar(select(HouseholdInvitation).where(HouseholdInvitation.id == invitation_id, HouseholdInvitation.household_id == household_id, HouseholdInvitation.status == "pending"))
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitación pendiente no encontrada")
    invitation.status = "cancelled"
    invitation.responded_at = datetime.now(timezone.utc)
    database.commit()
    database.refresh(invitation)
    return invitation_response(invitation, database)


@router.websocket("/ws/notifications")
async def notifications_websocket(websocket: WebSocket, token: str):
    try:
        payload = decode_token(token, "access")
    except Exception:
        await websocket.close(code=1008)
        return
    with SessionLocal() as database:
        user = database.scalar(select(User).where(User.username == payload["sub"]))
    if user is None:
        await websocket.close(code=1008)
        return
    await notification_manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        notification_manager.disconnect(user.id, websocket)
