"""Durable encrypted configuration for rewrite providers.

Secrets are accepted only at the write boundary, encrypted before persistence
and never returned by projections.  Model selection is public configuration.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsflow.persistence.models import RewriteProviderSettingModel
from newsflow.providers.model_catalog import ProviderModelCatalog
from newsflow.providers.openrouter import (
    FreeModelRequired,
    OpenRouterRewriteProvider,
    is_free_openrouter_model,
)
from newsflow.security.session_cipher import SessionCipher


class RewriteProviderSettingsService:
    def __init__(self, session: Session, *, cipher: SessionCipher) -> None:
        self._session = session
        self._cipher = cipher

    def list_settings(self) -> list[dict[str, object]]:
        return [
            self._project(row)
            for row in self._session.scalars(
                select(RewriteProviderSettingModel).order_by(RewriteProviderSettingModel.provider)
            )
        ]

    def configure_openrouter(
        self, *, api_key: str, fallback_models: tuple[str, ...]
    ) -> dict[str, object]:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        try:
            OpenRouterRewriteProvider(api_key="validation", fallback_models=fallback_models)
        except FreeModelRequired as exc:
            raise ValueError("OpenRouter rewrite models must be explicitly free") from exc
        return self._upsert(
            provider="OPENROUTER",
            api_key=api_key,
            primary_model=fallback_models[0],
            fallback_models=fallback_models,
        )

    def configure_openai(self, *, api_key: str, model: str) -> dict[str, object]:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("OpenAI API key is required")
        model = model.strip()
        if not model or len(model) > 255:
            raise ValueError("OpenAI rewrite model is invalid")
        return self._upsert(
            provider="OPENAI",
            api_key=api_key,
            primary_model=model,
            fallback_models=(),
        )

    def remove_provider(self, provider: str) -> dict[str, object]:
        if provider not in {"OPENAI", "OPENROUTER"}:
            raise ValueError("Unknown rewrite provider")
        try:
            row = self._session.get(RewriteProviderSettingModel, provider)
            if row is not None:
                self._session.delete(row)
            self._session.commit()
            return {"provider": provider, "configured": False}
        except Exception:
            self._session.rollback()
            raise

    def available_models(self, provider: str, *, catalog: ProviderModelCatalog) -> tuple[str, ...]:
        if provider not in {"OPENAI", "OPENROUTER"}:
            raise ValueError("Unknown rewrite provider")
        row = self._session.get(RewriteProviderSettingModel, provider)
        if row is None:
            raise LookupError("Rewrite provider is not configured")
        models = catalog.list_models(
            provider=provider, api_key=self._cipher.decrypt(row.encrypted_api_key)
        )
        if provider == "OPENROUTER":
            return tuple(model for model in models if is_free_openrouter_model(model))
        return models

    def _upsert(
        self,
        *,
        provider: str,
        api_key: str,
        primary_model: str,
        fallback_models: tuple[str, ...],
    ) -> dict[str, object]:
        try:
            row = self._session.get(RewriteProviderSettingModel, provider)
            if row is None:
                row = RewriteProviderSettingModel(
                    provider=provider,
                    encrypted_api_key=self._cipher.encrypt(api_key),
                    primary_model=primary_model,
                    fallback_models=",".join(fallback_models),
                )
                self._session.add(row)
            else:
                row.encrypted_api_key = self._cipher.encrypt(api_key)
                row.primary_model = primary_model
                row.fallback_models = ",".join(fallback_models)
            self._session.flush()
            result = self._project(row)
            self._session.commit()
            return result
        except Exception:
            self._session.rollback()
            raise

    @staticmethod
    def _project(row: RewriteProviderSettingModel) -> dict[str, object]:
        models = tuple(model for model in row.fallback_models.split(",") if model)
        return {
            "provider": row.provider,
            "configured": True,
            "primary_model": row.primary_model,
            "fallback_models": models,
        }
