from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def name_cannot_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class HouseholdResponse(BaseModel):
    id: int
    name: str
    role: str


class MemberResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: str


class InvitationCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    role: str = Field(default="member", pattern="^(member|owner)$")


class InvitationResponse(BaseModel):
    id: int
    household_id: int
    household_name: str
    invited_username: str
    invited_by_username: str
    role: str
    status: str
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None
