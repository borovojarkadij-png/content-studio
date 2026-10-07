"""Server-only construction from encrypted settings; no network in factory."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from newsflow.persistence.models import OutputChannel, RewriteProviderSettingModel
from newsflow.providers.openai_rewrite import OpenAIRewriteProvider, ProviderConfigurationInvalid
from newsflow.providers.openrouter import FreeModelRequired
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.security.session_cipher import SessionCipher, SessionDecryptionUnavailable


class ConfiguredRewriteProviderFactory:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        cipher: SessionCipher,
        opener=None,
        provider: str = "OPENAI",
    ):
        if provider not in {"OPENAI", "OPENROUTER"}:
            raise ProviderConfigurationInvalid("REWRITE_PROVIDER_INVALID")
        self._factory, self._cipher, self._opener = session_factory, cipher, opener
        self._provider = provider

    def __call__(self, channel_id: int) -> OpenAIRewriteProvider | StructuredFreeOpenRouterProvider:
        with self._factory() as session:
            channel = session.get(OutputChannel, channel_id)
            settings = session.get(RewriteProviderSettingModel, self._provider)
            if channel is None or settings is None:
                raise ProviderConfigurationInvalid("PROVIDER_OR_CHANNEL_NOT_CONFIGURED")
            try:
                key = self._cipher.decrypt(settings.encrypted_api_key)
            except SessionDecryptionUnavailable:
                raise ProviderConfigurationInvalid("REWRITE_SECRET_UNAVAILABLE") from None
            if self._provider == "OPENROUTER":
                try:
                    return StructuredFreeOpenRouterProvider(
                        api_key=key,
                        models=tuple(settings.fallback_models.split(",")),
                        style=channel.rewrite_style,
                        opener=self._opener,
                    )
                except FreeModelRequired:
                    raise ProviderConfigurationInvalid("FREE_MODEL_CONFIGURATION_INVALID") from None
            return OpenAIRewriteProvider(
                api_key=key,
                model=settings.primary_model,
                style=channel.rewrite_style,
                opener=self._opener,
            )
