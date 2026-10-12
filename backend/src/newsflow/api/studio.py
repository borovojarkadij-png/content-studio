"""Read-only observability; does not contact providers or reveal configuration secrets."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
from newsflow.services.editorial_history import INPUT_INVALID, EditorialHistoryReader
from newsflow.services.studio_overview import StudioOverviewReader

router = APIRouter(prefix="/api/studio", tags=["studio"])


def get_overview_reader() -> Iterator[StudioOverviewReader]:
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            yield StudioOverviewReader(session)
        except SQLAlchemyError:
            raise HTTPException(
                503, "Durable database is unavailable or requires migrations"
            ) from None


@router.get("/overview")
def overview(
    response: Response,
    reader: Annotated[StudioOverviewReader, Depends(get_overview_reader)],
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    return reader.read(now=datetime.now(UTC))


_PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def get_editorial_history_reader() -> Iterator[EditorialHistoryReader]:
    try:
        for session in database_session():
            if session is None:
                raise HTTPException(
                    503, "Diagnostic history is unavailable", headers=_PRIVATE_HEADERS
                )
            yield EditorialHistoryReader(session)
    except SQLAlchemyError:
        raise HTTPException(
            503, "Diagnostic history is unavailable", headers=_PRIVATE_HEADERS
        ) from None


@router.get("/editorial-classification-history")
def editorial_classification_history(
    request: Request,
    response: Response,
    reader: Annotated[EditorialHistoryReader, Depends(get_editorial_history_reader)],
) -> dict[str, object]:
    response.headers.update(_PRIVATE_HEADERS)
    try:
        query = request.query_params
        if any(len(query.getlist(key)) > 1 for key in query):
            raise ValueError(INPUT_INVALID)

        def integer(name, default=None):
            raw = query.get(name)
            if raw is None and default is not None:
                return default
            if raw is None or not raw.isascii() or not raw.isdecimal() or len(raw) > 19:
                raise ValueError(INPUT_INVALID)
            return int(raw)

        return reader.read(
            query.get("content_key"),
            integer("mapping_id"),
            limit=integer("limit", 25),
            before_job_id=integer("before_job_id") if "before_job_id" in query else None,
        )
    except LookupError:
        raise HTTPException(
            404, "Diagnostic history was not found", headers=_PRIVATE_HEADERS
        ) from None
    except ValueError as exc:
        status = 422 if str(exc) == INPUT_INVALID else 503
        detail = (
            "Invalid diagnostic history request"
            if status == 422
            else "Diagnostic history is unavailable"
        )
        raise HTTPException(status, detail, headers=_PRIVATE_HEADERS) from None
    except SQLAlchemyError:
        raise HTTPException(
            503, "Diagnostic history is unavailable", headers=_PRIVATE_HEADERS
        ) from None
