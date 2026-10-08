"""Read-only observability; does not contact providers or reveal configuration secrets."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
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
