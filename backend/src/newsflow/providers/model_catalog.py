"""Read-only provider model catalogs; they never perform a rewrite."""

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelCatalogUnavailable(RuntimeError):
    """The configured provider could not list models for the saved credential."""


class ProviderModelCatalog(Protocol):
    def list_models(self, *, provider: str, api_key: str) -> tuple[str, ...]: ...


@dataclass(frozen=True, slots=True)
class HttpProviderModelCatalog:
    openai_url: str = "https://api.openai.com/v1/models"
    openrouter_url: str = "https://openrouter.ai/api/v1/models"
    timeout_seconds: float = 20.0

    def list_models(self, *, provider: str, api_key: str) -> tuple[str, ...]:
        if provider == "OPENAI":
            records = self._request(self.openai_url, api_key)
            return tuple(sorted(self._model_ids(records)))
        if provider == "OPENROUTER":
            records = self._request(self.openrouter_url, api_key)
            return tuple(
                sorted(model for model in self._model_ids(records) if self._is_free(model))
            )
        raise ValueError("Unknown rewrite provider")

    def _request(self, url: str, api_key: str) -> object:
        request = Request(url, headers={"Authorization": f"Bearer {api_key}"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ModelCatalogUnavailable("Provider model catalog is unavailable") from exc

    @staticmethod
    def _model_ids(payload: object) -> tuple[str, ...]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ModelCatalogUnavailable("Provider model catalog has an invalid response")
        return tuple(
            record["id"]
            for record in payload["data"]
            if isinstance(record, dict)
            and isinstance(record.get("id"), str)
            and record["id"].strip()
        )

    @staticmethod
    def _is_free(model: str) -> bool:
        return model == "openrouter/free" or model.endswith(":free")
