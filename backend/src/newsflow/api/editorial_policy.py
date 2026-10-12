"""Authenticated persistent diagnostic policy; never grants execution authority."""

from collections.abc import Iterator
from json import JSONDecodeError
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
from newsflow.security.editorial_operator import (
    EditorialOperatorPrincipal,
    EditorialOperatorUnauthorized,
    EditorialOperatorUnavailable,
    authenticate_editorial_operator,
)
from newsflow.services.editorial_policy_configuration import (
    EditorialPolicyConfigurationService,
    EditorialPolicyConflict,
    EditorialPolicyInvalid,
)

router = APIRouter(prefix="/api/settings/editorial-policy", tags=["editorial-policy"])


def operator(authorization: Annotated[str | None, Header()] = None) -> EditorialOperatorPrincipal:
    try:
        return authenticate_editorial_operator(authorization)
    except EditorialOperatorUnavailable:
        raise HTTPException(503, "Editorial operator authentication unavailable") from None
    except EditorialOperatorUnauthorized:
        raise HTTPException(
            401,
            "Editorial operator authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


Principal = Annotated[EditorialOperatorPrincipal, Depends(operator)]


def policy_service(principal: Principal) -> Iterator[EditorialPolicyConfigurationService]:
    # Authentication is a dependency of session acquisition, never the reverse.
    try:
        for session in database_session():
            if session is None:
                raise HTTPException(503, "Editorial policy storage unavailable")
            yield EditorialPolicyConfigurationService(session)
    except EditorialPolicyConflict:
        raise HTTPException(409, "Editorial policy configuration conflict") from None
    except (EditorialPolicyInvalid, JSONDecodeError):
        raise HTTPException(422, "Invalid editorial policy configuration") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Editorial policy storage unavailable") from None


Service = Annotated[EditorialPolicyConfigurationService, Depends(policy_service)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ProtectedEntityRequest(StrictRequest):
    entity_id: str
    aliases: list[str]


class PolicyRequest(StrictRequest):
    enabled: bool
    provider: str
    model: str
    protected_entities: list[ProtectedEntityRequest]
    expected_etag: str | None


@router.get("")
def read_policy(service: Service):
    return service.read()


@router.put("")
def configure_policy(request: PolicyRequest, principal: Principal, service: Service):
    return service.configure(**request.model_dump(), actor_id=principal.actor_id)
