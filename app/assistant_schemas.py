from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantCommandResponse(BaseModel):
    id: int
    status: str
    transcript: str
    proposal: dict[str, Any]
    expires_at: datetime


class AssistantProposalUpdate(BaseModel):
    proposal: dict[str, Any] = Field(min_length=1)


class AssistantConfirmResponse(BaseModel):
    command_id: int
    status: Literal["confirmed"]
    result: dict[str, Any]
