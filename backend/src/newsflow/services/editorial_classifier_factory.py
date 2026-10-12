"""Fresh diagnostic admission and explicit encrypted credentials; no transport IO."""

from newsflow.persistence.models import RewriteProviderSettingModel
from newsflow.providers.editorial_classifier import (
    FreeOpenRouterEditorialClassifier,
    OpenAIEditorialClassifier,
)
from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid
from newsflow.security.session_cipher import SessionDecryptionUnavailable
from newsflow.services.editorial_admission import (
    EditorialAdmissionBinding,
    EditorialAdmissionBlocked,
    resolve_editorial_admission,
)


class ConfiguredEditorialClassifierFactory:
    def __init__(self, session_factory, *, cipher, opener=None):
        self._factory, self._cipher, self._opener = session_factory, cipher, opener

    def __call__(self, binding: EditorialAdmissionBinding):
        if type(binding) is not EditorialAdmissionBinding:
            raise ProviderConfigurationInvalid("EDITORIAL_BINDING_INVALID")
        with self._factory() as session:
            fresh = resolve_editorial_admission(
                session, content_key=binding.request.content_key, mapping_id=binding.mapping_id
            )
            if fresh != binding:
                raise EditorialAdmissionBlocked("EDITORIAL_BINDING_CHANGED")
            settings = session.get(RewriteProviderSettingModel, binding.provider)
            if (
                settings is None
                or type(settings.encrypted_api_key) is not str
                or not settings.encrypted_api_key.strip()
            ):
                raise ProviderConfigurationInvalid("EDITORIAL_SECRET_MISSING")
            try:
                key = self._cipher.decrypt(settings.encrypted_api_key)
            except (SessionDecryptionUnavailable, ValueError, TypeError):
                raise ProviderConfigurationInvalid("EDITORIAL_SECRET_UNAVAILABLE") from None
            if type(key) is not str or not key.strip() or "\n" in key or "\r" in key:
                raise ProviderConfigurationInvalid("EDITORIAL_SECRET_UNAVAILABLE")
        classifier = (
            OpenAIEditorialClassifier
            if binding.provider == "OPENAI"
            else FreeOpenRouterEditorialClassifier
        )
        return classifier(api_key=key, model=binding.model, opener=self._opener)
