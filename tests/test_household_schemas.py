import pytest
from pydantic import ValidationError

from app.household_schemas import HouseholdCreate, InvitationCreate
from app.schemas import RegisterRequest


def test_register_request_trims_display_name_and_username() -> None:
    request = RegisterRequest(username="  ana_1 ", display_name=" Ana ", password="a-secure-password")

    assert request.username == "ana_1"
    assert request.display_name == "Ana"


def test_register_request_rejects_weak_password_and_invalid_username() -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(username="ana", display_name="Ana", password="short")
    with pytest.raises(ValidationError):
        RegisterRequest(username="ana user", display_name="Ana", password="a-secure-password")


def test_household_and_invitation_validate_roles_and_blank_names() -> None:
    assert HouseholdCreate(name="  Casa  ").name == "Casa"
    assert InvitationCreate(username="ana", role="owner").role == "owner"
    with pytest.raises(ValidationError):
        HouseholdCreate(name="   ")
    with pytest.raises(ValidationError):
        InvitationCreate(username="ana", role="admin")
