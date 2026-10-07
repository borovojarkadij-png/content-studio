"""Secret-safe rewrite-provider settings API."""

from collections.abc import Iterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from newsflow.persistence.database import database_session
from newsflow.providers.model_catalog import (
    HttpProviderModelCatalog,
    ModelCatalogUnavailable,
    ProviderModelCatalog,
)
from newsflow.security.master_key import MasterKeyUnavailable, load_runtime_master_key
from newsflow.security.session_cipher import MasterKeyFormatInvalid, SessionCipher
from newsflow.services.rewrite_provider_settings import RewriteProviderSettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_rewrite_provider_settings_service() -> Iterator[RewriteProviderSettingsService]:
    for session in database_session():
        if session is None:
            raise HTTPException(503, "Durable database is not configured")
        try:
            cipher = SessionCipher(load_runtime_master_key())
        except (MasterKeyUnavailable, MasterKeyFormatInvalid) as exc:
            raise HTTPException(503, "Persistent secret store is unavailable") from exc
        try:
            yield RewriteProviderSettingsService(session, cipher=cipher)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        except SQLAlchemyError:
            raise HTTPException(
                503, "Durable database is unavailable or requires migrations"
            ) from None


Settings = Annotated[RewriteProviderSettingsService, Depends(get_rewrite_provider_settings_service)]


def get_provider_model_catalog() -> ProviderModelCatalog:
    return HttpProviderModelCatalog()


ModelCatalog = Annotated[ProviderModelCatalog, Depends(get_provider_model_catalog)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OpenRouterRewriteSettingsRequest(StrictRequest):
    api_key: str = Field(min_length=1, max_length=2048)
    fallback_models: tuple[str, ...] = Field(min_length=1, max_length=8)


class OpenAIRewriteSettingsRequest(StrictRequest):
    api_key: str = Field(min_length=1, max_length=2048)
    model: str = Field(min_length=1, max_length=255)


@router.get("/rewrite-providers")
def list_rewrite_providers(service: Settings) -> dict[str, list[dict[str, object]]]:
    return {"items": service.list_settings()}


@router.put("/rewrite-providers/openrouter")
def configure_openrouter_rewrite_provider(
    request: OpenRouterRewriteSettingsRequest, service: Settings
) -> dict[str, object]:
    return service.configure_openrouter(
        api_key=request.api_key, fallback_models=request.fallback_models
    )


@router.put("/rewrite-providers/openai")
def configure_openai_rewrite_provider(
    request: OpenAIRewriteSettingsRequest, service: Settings
) -> dict[str, object]:
    return service.configure_openai(api_key=request.api_key, model=request.model)


@router.get("/rewrite-providers/{provider}/models")
def list_rewrite_provider_models(
    provider: Literal["openai", "openrouter"],
    service: Settings,
    catalog: ModelCatalog,
) -> dict[str, tuple[str, ...]]:
    try:
        return {"items": service.available_models(provider.upper(), catalog=catalog)}
    except LookupError as exc:
        raise HTTPException(409, "Rewrite provider is not configured") from exc
    except ModelCatalogUnavailable as exc:
        raise HTTPException(503, "Provider model catalog is unavailable") from exc


@router.delete("/rewrite-providers/{provider}")
def remove_rewrite_provider(
    provider: Literal["openai", "openrouter"], service: Settings
) -> dict[str, object]:
    return service.remove_provider(provider.upper())
