"""Decrypt existing provider settings only after qualified verification gates."""

from newsflow.persistence.models import RewriteProviderSettingModel
from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid
from newsflow.providers.semantic_verifier import (
    FreeOpenRouterSemanticVerifier,
    OpenAISemanticVerifier,
)
from newsflow.security.session_cipher import SessionDecryptionUnavailable


class ConfiguredSemanticVerifierFactory:
    def __init__(self, session_factory, *, cipher, opener=None):
        self._factory, self._cipher, self._opener = session_factory, cipher, opener

    def __call__(self, release):
        if release.provider not in {"OPENAI", "OPENROUTER"}:
            raise ProviderConfigurationInvalid("SEMANTIC_PROVIDER_INVALID")
        with self._factory() as session:
            setting = session.get(RewriteProviderSettingModel, release.provider)
            if setting is None or not setting.encrypted_api_key:
                raise ProviderConfigurationInvalid("SEMANTIC_CREDENTIAL_NOT_CONFIGURED")
            try:
                key = self._cipher.decrypt(setting.encrypted_api_key)
            except (ValueError, PermissionError, SessionDecryptionUnavailable):
                raise ProviderConfigurationInvalid("SEMANTIC_CREDENTIAL_UNREADABLE") from None
        adapter = (
            OpenAISemanticVerifier
            if release.provider == "OPENAI"
            else FreeOpenRouterSemanticVerifier
        )
        return adapter(api_key=key, model=release.model, opener=self._opener)
