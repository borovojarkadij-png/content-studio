"""Strict authenticated canonical context and append-only review workflow."""

from collections.abc import Iterator
from dataclasses import asdict
from os import getenv
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
from newsflow.security.illustration_reviewer import (
    ReviewerPrincipal,
    ReviewerUnauthorized,
    ReviewerUnavailable,
    authenticate_reviewer,
)
from newsflow.services.illustration_presentation import IllustrationPresentation
from newsflow.services.illustration_review import IllustrationReviewWriter

router = APIRouter(prefix="/api/illustration-review", tags=["illustration-review"])


def reviewer(authorization: Annotated[str | None, Header()] = None) -> ReviewerPrincipal:
    try:
        return authenticate_reviewer(authorization)
    except ReviewerUnavailable:
        raise HTTPException(503, "Illustration reviewer authentication unavailable") from None
    except ReviewerUnauthorized:
        raise HTTPException(
            401,
            "Illustration reviewer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


Principal = Annotated[ReviewerPrincipal, Depends(reviewer)]


def writer(principal: Principal) -> Iterator[IllustrationReviewWriter]:
    root = getenv("NEWSFLOW_MEDIA_ROOT", "").strip()
    if not root:
        raise HTTPException(503, "Illustration media storage unavailable")
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            yield IllustrationReviewWriter(session, Path(root))
        except LookupError:
            raise HTTPException(404, "Illustration record not found") from None
        except PermissionError:
            raise HTTPException(409, "Illustration context or operation conflict") from None
        except (ValueError, TypeError):
            raise HTTPException(422, "Invalid illustration review request") from None
        except SQLAlchemyError:
            raise HTTPException(
                503, "Durable illustration storage unavailable; retry operation"
            ) from None


Writer = Annotated[IllustrationReviewWriter, Depends(writer)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BindingRequest(StrictRequest):
    candidate_id: int = Field(gt=0, le=2**63 - 1)
    output_channel_id: int = Field(gt=0, le=2**63 - 1)
    mapping_id: int = Field(gt=0, le=2**63 - 1)
    content_key: str = Field(min_length=1, max_length=255)
    source_revision_id: int = Field(gt=0, le=2**63 - 1)
    source_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    rewrite_output_id: int = Field(gt=0, le=2**63 - 1)
    draft_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    media_asset_id: int = Field(gt=0, le=2**63 - 1)
    media_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    asset_metadata_sha256: str = Field(pattern="^[0-9a-f]{64}$")


class OperationRequest(StrictRequest):
    operation_key: str = Field(min_length=1, max_length=128)
    review_note: str = Field(min_length=1, max_length=2048)


class ReviewRequest(OperationRequest):
    displayed_binding: BindingRequest
    verdict: Literal["APPROVED_ILLUSTRATION", "REJECTED", "UNCERTAIN"]
    illustration_acknowledged: bool


def presentation_service(principal: Principal) -> Iterator[IllustrationPresentation]:
    # Latest review is intentionally independent of source and media eligibility.
    root = Path(getenv("NEWSFLOW_MEDIA_ROOT", "").strip() or ".")
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            yield IllustrationPresentation(session, root)
        except LookupError:
            raise HTTPException(404, "Illustration record not found") from None
        except (PermissionError, ValueError, TypeError, OSError):
            raise HTTPException(
                409, "Current illustration presentation unavailable; reload"
            ) from None
        except SQLAlchemyError:
            raise HTTPException(503, "Durable illustration storage unavailable") from None


Presentation = Annotated[IllustrationPresentation, Depends(presentation_service)]


@router.get("/candidates/{candidate_id}/presentation")
def presentation(candidate_id: int, response: Response, service: Presentation):
    if not getenv("NEWSFLOW_MEDIA_ROOT", "").strip():
        raise HTTPException(503, "Illustration media storage unavailable")
    value, etag = service.presentation(candidate_id)
    response.headers.update({"Cache-Control": "no-store", "ETag": etag})
    return value


@router.get("/candidates/{candidate_id}/photo")
def photo(
    candidate_id: int, service: Presentation, if_match: Annotated[str | None, Header()] = None
):
    if not getenv("NEWSFLOW_MEDIA_ROOT", "").strip():
        raise HTTPException(503, "Illustration media storage unavailable")
    if if_match is None:
        raise HTTPException(409, "Matching presentation validator required")
    content, mime, etag = service.photo(candidate_id, if_match)
    return Response(
        content,
        media_type=mime,
        headers={"Cache-Control": "no-store", "ETag": etag, "X-Content-Type-Options": "nosniff"},
    )


@router.get("/candidates/{candidate_id}/latest-review")
def latest_review(candidate_id: int, response: Response, service: Presentation):
    response.headers["Cache-Control"] = "no-store"
    return {"latest_review": service.latest(candidate_id)}


@router.get("/candidates/{candidate_id}")
def context(candidate_id: int, response: Response, service: Writer):
    response.headers["Cache-Control"] = "no-store"
    return {"binding": asdict(service.context(candidate_id))}


@router.post("/candidates/{candidate_id}/reviews")
def review(
    candidate_id: int,
    request: ReviewRequest,
    response: Response,
    principal: Principal,
    service: Writer,
):
    response.headers["Cache-Control"] = "no-store"
    if candidate_id != request.displayed_binding.candidate_id:
        raise HTTPException(409, "Illustration displayed candidate conflict")
    return service.review(principal, **request.model_dump())


@router.post("/records/{review_id}/revocations")
def revoke(
    review_id: int,
    request: OperationRequest,
    response: Response,
    principal: Principal,
    service: Writer,
):
    response.headers["Cache-Control"] = "no-store"
    return service.revoke(principal, review_id=review_id, **request.model_dump())
