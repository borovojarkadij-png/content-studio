import io
import json
from urllib.error import HTTPError

import pytest

from newsflow.providers.openai_rewrite import ProviderConfigurationInvalid, ProviderResponseInvalid
from newsflow.providers.openrouter import FreeModelRequired, ProviderUnavailable


def reply(text="Открыто 10 объектов"):
    return {
        "id": "synthetic",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"rewritten_text": text})},
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


class FreeHttp:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append(json.loads(request.data))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return io.BytesIO(json.dumps(result).encode())


def client(http, **options):
    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    return StructuredFreeOpenRouterProvider(
        api_key="synthetic", models=("a/model:free", "b/model:free"), opener=http, **options
    )


def test_free_structured_failover_sets_zero_price_caps_and_records_used_free_model():
    http = FreeHttp([HTTPError("https://synthetic", 429, "private-key", {}, None), reply()])
    provider = client(http, style="TABLOID")
    assert provider.rewrite("Открыто 10 объектов") == "Открыто 10 объектов"
    assert [request["model"] for request in http.requests] == ["a/model:free", "b/model:free"]
    for request in http.requests:
        assert request["provider"]["max_price"] == {"prompt": 0, "completion": 0, "request": 0}
        assert request["provider"]["allow_fallbacks"] is False
        assert request["provider"]["require_parameters"] is True
        assert request["response_format"]["json_schema"]["strict"] is True
        assert "tabloid" in request["messages"][0]["content"]
    assert provider.last_usage.model == "b/model:free"
    assert provider.last_usage.provider == "OPENROUTER"
    assert provider.last_usage.input_tokens == 100


@pytest.mark.parametrize(
    "models", [("paid/model",), ("a/model:free",) * 2, tuple(f"a/{n}:free" for n in range(9))]
)
def test_invalid_paid_duplicate_or_unbounded_model_lists_have_zero_calls(models):
    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    http = FreeHttp([])
    with pytest.raises(FreeModelRequired):
        StructuredFreeOpenRouterProvider(api_key="synthetic", models=models, opener=http)
    assert http.requests == []


@pytest.mark.parametrize("status", [401, 403])
def test_bad_credentials_do_not_try_other_models(status):
    http = FreeHttp([HTTPError("https://synthetic", status, "private-key", {}, None), reply()])
    with pytest.raises(ProviderConfigurationInvalid):
        client(http).rewrite("source")
    assert len(http.requests) == 1


@pytest.mark.parametrize("kind", ["malformed", "truncated", "refusal", "paid_cost"])
def test_invalid_content_is_not_repaired_by_fallback(kind):
    body = reply()
    if kind == "malformed":
        body["choices"][0]["message"]["content"] = "not JSON"
    elif kind == "truncated":
        body["choices"][0]["finish_reason"] = "length"
    elif kind == "refusal":
        body["choices"][0]["message"]["refusal"] = "no"
    else:
        body["usage"]["cost"] = 0.01
    http = FreeHttp([body, reply()])
    with pytest.raises(ProviderResponseInvalid):
        client(http).rewrite("source")
    assert len(http.requests) == 1


def test_one_overall_deadline_prevents_fallback_after_budget_is_consumed():
    elapsed = [0.0]
    http = FreeHttp([HTTPError("https://synthetic", 503, "private-key", {}, None), reply()])

    def open_after_budget(request, *, timeout):
        elapsed[0] = 31
        return http(request, timeout=timeout)

    from newsflow.providers.openrouter_structured import StructuredFreeOpenRouterProvider

    provider = StructuredFreeOpenRouterProvider(
        api_key="synthetic",
        models=("a/model:free", "b/model:free"),
        opener=open_after_budget,
        clock=lambda: elapsed[0],
    )
    with pytest.raises(ProviderUnavailable):
        provider.rewrite("source")
    assert len(http.requests) == 1


def test_free_tabloid_mode_cannot_rewrite_editorial_reject_or_repair_changed_facts():
    from newsflow.domain.editorial import EditorialGate
    from newsflow.services.fact_guard import FactPreservationBlocked
    from newsflow.services.rewrite import EditorialRewriteBlocked, RewriteService

    http = FreeHttp([reply("Открыто 20 объектов"), reply()])
    service = RewriteService(client(http, style="TABLOID"))
    rejected = EditorialGate().evaluate(
        text="hostile", protected_entities=("Protected",), sentiment="negative", framing="hostile"
    )
    with pytest.raises(EditorialRewriteBlocked):
        service.rewrite("hostile", rejected)
    assert http.requests == []
    permitted = EditorialGate().evaluate(
        text="Открыто 10 объектов", protected_entities=(), sentiment="neutral", framing="neutral"
    )
    with pytest.raises(FactPreservationBlocked):
        service.rewrite("Открыто 10 объектов", permitted)
    assert len(http.requests) == 1
