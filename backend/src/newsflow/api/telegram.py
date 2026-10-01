"""Minimal Telegram configuration API; state changes remain service-owned."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from newsflow.domain.telegram import parse_donor_import
from newsflow.services.telegram_configuration import TelegramConfigurationService

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
configuration_service = TelegramConfigurationService()


class DonorBulkImportRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class TelegramAccountCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    telegram_user_id: int
    encrypted_session: str = Field(min_length=1)


@router.post("/donors:bulk-import")
def bulk_import_donors(request: DonorBulkImportRequest) -> dict[str, list[str]]:
    result = parse_donor_import(request.raw_text)
    return {
        "accepted": [entry.canonical_identifier for entry in result.accepted],
        "rejected": list(result.rejected),
    }


@router.get("/accounts")
def list_accounts() -> dict[str, list[object]]:
    return {"items": []}


@router.post("/accounts", status_code=201)
def create_account(request: TelegramAccountCreateRequest) -> dict[str, object]:
    account = configuration_service.create_account(
        request.name, request.telegram_user_id, request.encrypted_session
    )
    return {"name": account.name, "telegram_user_id": account.telegram_user_id}


@router.get("/incoming-posts")
def list_incoming_posts() -> dict[str, list[object]]:
    """Moderation inbox contract; persistence-backed query is added next."""
    return {"items": []}
