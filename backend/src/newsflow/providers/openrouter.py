"""Free-only OpenRouter rewrite adapter with deterministic local failover.

The API key remains runtime-only and is never included in result objects or
exceptions.  A channel's configured model list is validated before requests so
OpenRouter can never silently use a paid fallback.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class FreeModelRequired(ValueError):
    """Raised when a configured fallback could incur paid OpenRouter usage."""


class ProviderUnavailable(RuntimeError):
    """A model could not serve a request and the next allowed fallback may run."""


class OpenRouterTransport(Protocol):
    def rewrite(self, *, api_key: str, model: str, text: str) -> str: ...


@dataclass(frozen=True, slots=True)
class HttpOpenRouterTransport:
    endpoint: str = "https://openrouter.ai/api/v1/chat/completions"
    timeout_seconds: float = 30.0

    def rewrite(self, *, api_key: str, model: str, text: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Rewrite this Telegram post without adding facts:\n\n" + text,
                    }
                ],
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderUnavailable("OpenRouter model is unavailable") from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as exc:
            raise ProviderUnavailable("OpenRouter response has no rewrite content") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderUnavailable("OpenRouter response has no rewrite content")
        return content


def _is_free_model(model: str) -> bool:
    return model == "openrouter/free" or model.endswith(":free")


class OpenRouterRewriteProvider:
    """Rewrite through configured free-only models, in deterministic order."""

    def __init__(
        self,
        *,
        api_key: str,
        fallback_models: Sequence[str],
        transport: OpenRouterTransport | None = None,
    ) -> None:
        models = tuple(model.strip() for model in fallback_models)
        if not api_key.strip():
            raise ValueError("OpenRouter API key is required")
        if (
            not models
            or len(models) != len(set(models))
            or any(not _is_free_model(model) for model in models)
        ):
            raise FreeModelRequired("Only explicit OpenRouter free models are allowed")
        self._api_key = api_key
        self._models = models
        self._transport = transport or HttpOpenRouterTransport()

    def rewrite(self, text: str) -> str:
        last_error: ProviderUnavailable | None = None
        for model in self._models:
            try:
                return self._transport.rewrite(api_key=self._api_key, model=model, text=text)
            except ProviderUnavailable as exc:
                last_error = exc
        raise ProviderUnavailable(
            "No configured free OpenRouter model is available"
        ) from last_error
