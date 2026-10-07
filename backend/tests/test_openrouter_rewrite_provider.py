import pytest

from newsflow.providers.openrouter import (
    FreeModelRequired,
    OpenRouterRewriteProvider,
    ProviderUnavailable,
)


class ScriptedTransport:
    def __init__(self, responses: dict[str, str | Exception]) -> None:
        self._responses = responses
        self.models: list[str] = []

    def rewrite(self, *, api_key: str, model: str, text: str) -> str:
        assert api_key == "test-key"
        self.models.append(model)
        response = self._responses[model]
        if isinstance(response, Exception):
            raise response
        return response


def test_openrouter_uses_next_free_model_when_primary_is_unavailable() -> None:
    transport = ScriptedTransport(
        {
            "alpha/free-model:free": ProviderUnavailable("rate limited"),
            "beta/rewrite:free": "rewritten text",
        }
    )
    provider = OpenRouterRewriteProvider(
        api_key="test-key",
        fallback_models=("alpha/free-model:free", "beta/rewrite:free"),
        transport=transport,
    )

    assert provider.rewrite("source text") == "rewritten text"
    assert transport.models == ["alpha/free-model:free", "beta/rewrite:free"]


def test_openrouter_refuses_paid_or_unqualified_model_before_any_network_attempt() -> None:
    transport = ScriptedTransport({"openai/gpt-5": "must not be used"})

    with pytest.raises(FreeModelRequired):
        OpenRouterRewriteProvider(
            api_key="test-key", fallback_models=("openai/gpt-5",), transport=transport
        )

    assert transport.models == []


def test_openrouter_free_router_is_allowed_as_a_free_only_policy() -> None:
    transport = ScriptedTransport({"openrouter/free": "free output"})
    provider = OpenRouterRewriteProvider(
        api_key="test-key", fallback_models=("openrouter/free",), transport=transport
    )

    assert provider.rewrite("source text") == "free output"
