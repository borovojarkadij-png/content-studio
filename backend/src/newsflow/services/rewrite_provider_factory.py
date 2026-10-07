"""Server-only construction from encrypted settings; no network in factory."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from newsflow.persistence.models import OutputChannel, RewriteProviderSettingModel
from newsflow.providers.openai_rewrite import OpenAIRewriteProvider, ProviderConfigurationInvalid
from newsflow.security.session_cipher import SessionCipher, SessionDecryptionUnavailable


class ConfiguredRewriteProviderFactory:
    def __init__(
        self, session_factory: Callable[[], Session], *, cipher: SessionCipher, opener=None
    ):
        self._factory, self._cipher, self._opener = session_factory, cipher, opener

    def __call__(self, channel_id: int) -> OpenAIRewriteProvider:
        with self._factory() as session:
            channel = session.get(OutputChannel, channel_id)
            settings = session.get(RewriteProviderSettingModel, "OPENAI")
            if channel is None or settings is None:
                raise ProviderConfigurationInvalid("OPENAI_OR_CHANNEL_NOT_CONFIGURED")
            try:
                key = self._cipher.decrypt(settings.encrypted_api_key)
            except SessionDecryptionUnavailable:
                raise ProviderConfigurationInvalid("OPENAI_SECRET_UNAVAILABLE") from None
            return OpenAIRewriteProvider(
                api_key=key,
                model=settings.primary_model,
                style=channel.rewrite_style,
                opener=self._opener,
            )
