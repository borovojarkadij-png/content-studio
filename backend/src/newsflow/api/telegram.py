"""Minimal Telegram configuration API; state changes remain service-owned."""

from collections.abc import Iterator
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
from newsflow.services.moderation_inbox import ModerationInboxReader
from newsflow.services.publication_planning import (
    CandidateBlocked,
    PlanValidationError,
    PublicationPlanningService,
)
from newsflow.services.telegram_configuration import (
    ConfigurationConflict,
    TelegramConfigurationService,
)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def get_configuration_service() -> Iterator[TelegramConfigurationService]:
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            yield TelegramConfigurationService(session)
        except ConfigurationConflict as exc:
            raise HTTPException(409, str(exc)) from None
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except SQLAlchemyError:
            raise HTTPException(
                503, "Durable database is unavailable or requires migrations"
            ) from None


Configuration = Annotated[TelegramConfigurationService, Depends(get_configuration_service)]


def get_publication_planning_service() -> Iterator[PublicationPlanningService]:
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            yield PublicationPlanningService(session)
        except CandidateBlocked as exc:
            raise HTTPException(409, str(exc)) from None
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from None
        except PlanValidationError as exc:
            raise HTTPException(422, str(exc)) from None
        except SQLAlchemyError:
            raise HTTPException(
                503, "Durable database is unavailable or requires migrations"
            ) from None


PublicationPlanning = Annotated[
    PublicationPlanningService, Depends(get_publication_planning_service)
]


def get_moderation_inbox_reader() -> Iterator[ModerationInboxReader | None]:
    """Create a request-scoped durable inbox reader when DATABASE_URL is set."""
    for session in database_session():
        yield ModerationInboxReader(session) if session is not None else None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DonorBulkImportRequest(StrictRequest):
    telegram_account_id: int = Field(gt=0, strict=True)
    raw_text: str = Field(min_length=1, max_length=100000)


class TelegramAccountUpdateRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=100)


class TelegramAccountCreateRequest(TelegramAccountUpdateRequest):
    telegram_user_id: int = Field(gt=0, lt=2**63, strict=True)


class ChannelUpdateRequest(StrictRequest):
    title: str = Field(min_length=1, max_length=255)


class ChannelCreateRequest(ChannelUpdateRequest):
    telegram_account_id: int = Field(gt=0, strict=True)
    telegram_channel_id: int = Field(ge=-(2**63), lt=2**63, strict=True)


class MappingUpdateRequest(StrictRequest):
    intake_percent: int = Field(ge=0, le=100, strict=True)
    target_mix_percent: int = Field(ge=0, le=100, strict=True)
    eligibility_mode: Literal["IMMEDIATE", "DELAYED"] | None = None
    delay_minutes: int | None = Field(default=None, ge=0, le=10080, strict=True)
    priority: int | None = Field(default=None, ge=-1000, le=1000, strict=True)
    media_policy: Literal["REUSE_SOURCE", "LICENSED_LIBRARY"] | None = None


class MappingCreateRequest(MappingUpdateRequest):
    donor_channel_id: int = Field(gt=0, strict=True)
    output_channel_id: int = Field(gt=0, strict=True)
    eligibility_mode: Literal["IMMEDIATE", "DELAYED"] = "IMMEDIATE"
    delay_minutes: int = Field(default=0, ge=0, le=10080, strict=True)
    priority: int = Field(default=0, ge=-1000, le=1000, strict=True)
    media_policy: Literal["REUSE_SOURCE", "LICENSED_LIBRARY"] = "REUSE_SOURCE"


class PublicationPlanRequest(StrictRequest):
    mode: Literal["MANUAL", "AUTOMATIC"]
    daily_limit: int = Field(ge=1, le=24, strict=True)
    slot_minutes: tuple[int, ...] = Field(min_length=1, max_length=24)
    timezone: str = Field(min_length=1, max_length=64)


class PlanDayRequest(StrictRequest):
    day: date


@router.post("/donors:bulk-import")
def bulk_import_donors(
    request: DonorBulkImportRequest, service: Configuration
) -> dict[str, object]:
    return service.bulk_import_donors(request.telegram_account_id, request.raw_text)


@router.get("/accounts")
def list_accounts(service: Configuration) -> dict[str, list]:
    return {"items": service.list_accounts()}


@router.post("/accounts", status_code=201)
def create_account(
    request: TelegramAccountCreateRequest, service: Configuration
) -> dict[str, object]:
    return service.create_account(request.name, request.telegram_user_id)


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: int, request: TelegramAccountUpdateRequest, service: Configuration
) -> dict[str, object]:
    return service.update_account(account_id, request.name)


@router.get("/donors")
def list_donors(service: Configuration) -> dict[str, list]:
    return {"items": service.list_donors()}


@router.post("/donors", status_code=201)
def create_donor(request: ChannelCreateRequest, service: Configuration) -> dict[str, object]:
    return service.create_donor(
        request.telegram_account_id, request.telegram_channel_id, request.title
    )


@router.patch("/donors/{donor_id}")
def update_donor(
    donor_id: int, request: ChannelUpdateRequest, service: Configuration
) -> dict[str, object]:
    return service.update_donor(donor_id, request.title)


@router.get("/output-channels")
def list_outputs(service: Configuration) -> dict[str, list]:
    return {"items": service.list_outputs()}


@router.post("/output-channels", status_code=201)
def create_output(request: ChannelCreateRequest, service: Configuration) -> dict[str, object]:
    return service.create_output(
        request.telegram_account_id, request.telegram_channel_id, request.title
    )


@router.patch("/output-channels/{output_id}")
def update_output(
    output_id: int, request: ChannelUpdateRequest, service: Configuration
) -> dict[str, object]:
    return service.update_output(output_id, request.title)


@router.get("/mappings")
def list_mappings(service: Configuration) -> dict[str, list]:
    return {"items": service.list_mappings()}


@router.post("/mappings", status_code=201)
def create_mapping(request: MappingCreateRequest, service: Configuration) -> dict[str, object]:
    return service.create_mapping(
        request.donor_channel_id,
        request.output_channel_id,
        request.intake_percent,
        request.target_mix_percent,
        eligibility_mode=request.eligibility_mode,
        delay_minutes=request.delay_minutes,
        priority=request.priority,
        media_policy=request.media_policy,
    )


@router.patch("/mappings/{mapping_id}")
def update_mapping(
    mapping_id: int, request: MappingUpdateRequest, service: Configuration
) -> dict[str, object]:
    return service.update_mapping(
        mapping_id,
        request.intake_percent,
        request.target_mix_percent,
        eligibility_mode=request.eligibility_mode,
        delay_minutes=request.delay_minutes,
        priority=request.priority,
        media_policy=request.media_policy,
    )


@router.get("/donor-imports")
def list_donor_imports(service: Configuration) -> dict[str, list]:
    return {"items": service.list_donor_imports()}


@router.put("/output-channels/{output_channel_id}/publication-plan")
def configure_publication_plan(
    output_channel_id: int, request: PublicationPlanRequest, service: PublicationPlanning
) -> dict[str, object]:
    return service.configure_plan(
        output_channel_id,
        request.mode,
        request.daily_limit,
        request.slot_minutes,
        request.timezone,
    )


@router.post("/publication-plans/{plan_id}:plan-day")
def plan_publications_for_day(
    plan_id: int, request: PlanDayRequest, service: PublicationPlanning
) -> dict[str, list[dict[str, object]]]:
    return {"items": service.plan_day(plan_id, request.day)}


@router.get("/incoming-posts")
def list_incoming_posts(
    reader: Annotated[ModerationInboxReader | None, Depends(get_moderation_inbox_reader)],
) -> dict[str, list[object]]:
    return {"items": [] if reader is None else [item.as_dict() for item in reader.list_items()]}
