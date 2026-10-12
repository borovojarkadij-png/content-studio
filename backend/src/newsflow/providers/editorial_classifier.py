"""Classification-only adapters; synthetic contract conformance is not qualification."""

import json
import re

from newsflow.providers.openai_rewrite import (
    OpenAIRewriteProvider,
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
    RewriteUsage,
)
from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider
from newsflow.services.editorial_classification import (
    PROMPT_VERSION,
    EditorialClassificationReport,
    EditorialClassificationRequest,
    assess_editorial_classification,
    editorial_evidence_schema,
)


class _EditorialClassifier:
    prompt_version = PROMPT_VERSION

    def __init__(self, transport, model: str):
        self._transport = transport
        self._model = model
        self._last_usage: RewriteUsage | None = None
        self._last_response_model: str | None = None
        self._last_evidence_json: str | None = None

    @property
    def model(self) -> str:
        return self._model

    @property
    def last_usage(self) -> RewriteUsage | None:
        return self._last_usage

    @property
    def last_response_model(self) -> str | None:
        return self._last_response_model

    @property
    def last_evidence_json(self) -> str | None:
        return self._last_evidence_json

    def classify(self, request: EditorialClassificationRequest) -> EditorialClassificationReport:
        self._last_usage = None
        self._last_response_model = None
        self._last_evidence_json = None
        if type(request) is not EditorialClassificationRequest:
            raise ProviderConfigurationInvalid("EDITORIAL_REQUEST_INVALID")
        payload = json.dumps(request.payload, ensure_ascii=False)
        if len(payload) > 131072 or len(payload.encode("utf-8")) > 262144:
            raise ProviderConfigurationInvalid("EDITORIAL_REQUEST_TOO_LARGE")
        try:
            value = self._transport.generate_json(
                payload,
                instructions=request.messages[0]["content"],
                schema=editorial_evidence_schema(),
                name="newsflow_editorial_classification",
            )
        except RecursionError:
            raise ProviderResponseInvalid("EDITORIAL_EVIDENCE_INVALID") from None
        finally:
            # Transport clears usage before attempting IO; local failures above never copy it.
            self._last_usage = self._transport.last_usage
        actual = self._transport.last_response_model
        allowed = (self.model,)
        if self.provider == "OPENROUTER":
            allowed += (self.model.removesuffix(":free"),)
        if type(actual) is not str or actual not in allowed:
            raise ProviderResponseInvalid("EDITORIAL_RETURNED_MODEL_INVALID")
        self._last_response_model = actual
        try:
            raw = json.dumps(
                value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
            )
            size = len(raw.encode("utf-8"))
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ProviderResponseInvalid("EDITORIAL_EVIDENCE_INVALID") from None
        if size > 262144:
            raise ProviderResponseInvalid("EDITORIAL_EVIDENCE_TOO_LARGE")
        self._last_evidence_json = raw
        return assess_editorial_classification(request, raw)


class OpenAIEditorialClassifier(_EditorialClassifier):
    provider = "OPENAI"

    def __init__(self, *, api_key: str, model: str, opener=None):
        super().__init__(OpenAIRewriteProvider(api_key=api_key, model=model, opener=opener), model)


class FreeOpenRouterEditorialClassifier(_EditorialClassifier):
    provider = "OPENROUTER"

    def __init__(self, *, api_key: str, model: str, opener=None):
        if (
            type(model) is not str
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", model)
            or not model.endswith(":free")
        ):
            raise ProviderConfigurationInvalid("EDITORIAL_MODEL_INVALID")
        super().__init__(
            StructuredFreeOpenRouterProvider(api_key=api_key, models=(model,), opener=opener),
            model,
        )
