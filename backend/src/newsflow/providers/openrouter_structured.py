"""Free-only strict chat rewriting with one bounded local failover budget."""

import json
import re
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from newsflow.providers.openai_rewrite import (
    NoRedirect,
    ProviderConfigurationInvalid,
    ProviderResponseInvalid,
    RewriteUsage,
    rewrite_instructions,
    unique_json_object,
)
from newsflow.providers.openrouter import (
    FreeModelRequired,
    ProviderUnavailable,
    is_free_openrouter_model,
)
from newsflow.services.fact_guard import FactGuard


class StructuredFreeOpenRouterProvider:
    def __init__(
        self,
        *,
        api_key: str,
        models: tuple[str, ...],
        style="NEUTRAL",
        opener=None,
        clock=monotonic,
    ):
        if (
            not 1 <= len(models) <= 8
            or len(set(models)) != len(models)
            or any(
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}", model)
                or not is_free_openrouter_model(model)
                for model in models
            )
        ):
            raise FreeModelRequired("Only bounded unique explicit free models are allowed")
        if not api_key.strip() or "\r" in api_key or "\n" in api_key:
            raise ProviderConfigurationInvalid("OPENROUTER_KEY_INVALID")
        if style not in {"NEUTRAL", "TABLOID"}:
            raise ProviderConfigurationInvalid("REWRITE_STYLE_INVALID")
        self._key, self._models, self._style = api_key, models, style
        self._open, self._clock = opener or build_opener(NoRedirect()).open, clock
        self.last_usage: RewriteUsage | None = None

    def rewrite(self, text: str) -> str:
        self.last_usage = None
        FactGuard().validate_source(text)
        deadline = self._clock() + 30
        for model in self._models:
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise ProviderUnavailable("OPENROUTER_BUDGET_EXHAUSTED")
            payload = {
                "model": model,
                "max_tokens": 4096,
                "stream": False,
                "messages": [
                    {"role": "system", "content": rewrite_instructions(self._style)},
                    {"role": "user", "content": text},
                ],
                "provider": {
                    "require_parameters": True,
                    "allow_fallbacks": False,
                    "max_price": {"prompt": 0, "completion": 0, "request": 0},
                },
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "newsflow_rewrite",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {"rewritten_text": {"type": "string"}},
                            "required": ["rewritten_text"],
                            "additionalProperties": False,
                        },
                    },
                },
            }
            request = Request(
                "https://openrouter.ai/api/v1/chat/completions",
                method="POST",
                data=json.dumps(payload).encode(),
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with self._open(request, timeout=min(10, remaining)) as response:
                    raw = bytearray()
                    while True:
                        if self._clock() >= deadline:
                            raise ProviderUnavailable("OPENROUTER_BUDGET_EXHAUSTED")
                        chunk = response.read1(min(8192, 262145 - len(raw)))
                        raw.extend(chunk)
                        if len(raw) > 262144:
                            raise ProviderResponseInvalid("OPENROUTER_RESPONSE_TOO_LARGE")
                        if not chunk:
                            break
            except HTTPError as error:
                status = error.code
                error.close()
                if status in (401, 403):
                    raise ProviderConfigurationInvalid("OPENROUTER_CREDENTIAL_INVALID") from None
                if status in (400, 404, 408, 422, 429, 500, 502, 503, 504):
                    continue
                raise ProviderResponseInvalid("OPENROUTER_HTTP_INVALID") from None
            except (URLError, TimeoutError, OSError):
                continue
            return self._parse(raw, model)
        raise ProviderUnavailable("OPENROUTER_FREE_MODELS_UNAVAILABLE")

    def _parse(self, raw: bytes, model: str) -> str:
        try:
            body = json.loads(raw, object_pairs_hook=unique_json_object)
            usage = body["usage"]
            input_count, output_count = usage["prompt_tokens"], usage["completion_tokens"]
            cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
            total = usage["total_tokens"]
            if (
                any(
                    type(value) is not int or not 0 <= value <= 10000000
                    for value in (input_count, output_count, cached, total)
                )
                or cached > input_count
                or total != input_count + output_count
            ):
                raise ProviderResponseInvalid("OPENROUTER_USAGE_INVALID")
            self.last_usage = RewriteUsage(
                model, input_count, cached, output_count, None, self._style, "OPENROUTER"
            )
            if "error" in body and body["error"] is not None:
                raise ProviderResponseInvalid("OPENROUTER_RESPONSE_ERROR")
            if "cost" in usage and usage["cost"] != 0:
                raise ProviderResponseInvalid("OPENROUTER_UNEXPECTED_COST")
            choices = body["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise ProviderResponseInvalid("OPENROUTER_INCOMPLETE")
            message = choices[0]["message"]
            if message.get("refusal"):
                raise ProviderResponseInvalid("OPENROUTER_REFUSED")
            value = json.loads(message["content"], object_pairs_hook=unique_json_object)
            if not isinstance(value, dict) or set(value) != {"rewritten_text"}:
                raise ProviderResponseInvalid("OPENROUTER_SCHEMA_INVALID")
            result = value["rewritten_text"]
            if not isinstance(result, str) or not result.strip() or len(result) > 32000:
                raise ProviderResponseInvalid("OPENROUTER_TEXT_INVALID")
            return result
        except (KeyError, TypeError, ValueError, IndexError, AttributeError, UnicodeDecodeError):
            raise ProviderResponseInvalid("OPENROUTER_RESPONSE_INVALID") from None
