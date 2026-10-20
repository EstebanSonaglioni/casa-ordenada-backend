from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
    database: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials, "access")
    except Exception as error:
        raise HTTPException(status_code=401, detail="Invalid access token") from error
    user = database.scalar(select(User).where(User.username == payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def tokens_for(username: str, role: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(username, role),
        refresh_token=create_refresh_token(username, role),
        username=username,
        role=role,
    )


@router.post("/login", response_model=TokenResponse)
def login(credentials: LoginRequest, database: Session = Depends(get_db)) -> TokenResponse:
    user = database.scalar(select(User).where(User.username == credentials.username))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return tokens_for(user.username, user.role)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: RegisterRequest, database: Session = Depends(get_db)) -> TokenResponse:
    username = data.username.strip()
    if database.scalar(select(User.id).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail="El nombre de usuario ya está en uso")
    user = User(
        username=username,
        display_name=data.display_name.strip(),
        password_hash=hash_password(data.password),
        role="member",
    )
    database.add(user)
    database.commit()
    database.refresh(user)
    return tokens_for(user.username, user.role)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest) -> TokenResponse:
    try:
        payload = decode_token(request.refresh_token, "refresh")
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from error
    return tokens_for(payload["sub"], payload.get("role", "member"))
