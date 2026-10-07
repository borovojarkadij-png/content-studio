import json

import pytest
from test_openai_rewrite_provider import HttpFixture, envelope
from test_openrouter_structured import FreeHttp, reply

from newsflow.providers.openai_rewrite import ProviderResponseInvalid
from newsflow.services.semantic_facts import assess_semantic_facts

SOURCE = "Factory opened 3 lines."
DRAFT = "3 lines opened at the factory."


def assessment():
    return {
        "verdict": "PRESERVED",
        "source_complete": True,
        "draft_complete": True,
        "claims": [{"source_quote": SOURCE, "draft_quote": DRAFT, "relation": "SUPPORTED"}],
    }


def test_openai_semantic_verifier_uses_separate_strict_evidence_prompt_and_known_usage():
    from newsflow.providers.semantic_verifier import OpenAISemanticVerifier

    body = envelope()
    body["output"][0]["content"][0]["text"] = json.dumps(assessment())
    http = HttpFixture(body)
    verifier = OpenAISemanticVerifier(api_key="synthetic", model="synthetic-model", opener=http)
    result = verifier.verify(SOURCE, DRAFT)
    assert assess_semantic_facts(SOURCE, DRAFT, result).eligible is True
    request = json.loads(http.requests[0].data)
    assert request["store"] is False
    assert request["text"]["format"]["name"] == "newsflow_semantic_facts"
    assert request["text"]["format"]["strict"] is True
    assert "polarity" in request["input"][0]["content"]
    assert "untrusted" in request["input"][0]["content"]
    assert json.loads(request["input"][1]["content"]) == {"source": SOURCE, "draft": DRAFT}
    assert verifier.last_usage.input_tokens == 100
    assert verifier.last_usage.model == "synthetic-model"


@pytest.mark.parametrize(
    "kind", ["refusal", "bad-schema", "model-mismatch", "duplicate", "changed-anchor"]
)
def test_openai_verifier_fails_closed_without_repair_or_extra_calls(kind):
    from newsflow.providers.semantic_verifier import OpenAISemanticVerifier

    body = envelope()
    body["output"][0]["content"][0]["text"] = json.dumps(assessment())
    if kind == "refusal":
        body["output"][0]["content"][0]["type"] = "refusal"
    elif kind == "bad-schema":
        body["output"][0]["content"][0]["text"] = '{"verdict":"PRESERVED"}'
    elif kind == "model-mismatch":
        body["model"] = "unqualified-model"
    elif kind == "duplicate":
        body["output"][0]["content"][0]["text"] = '{"verdict":"CHANGED","verdict":"PRESERVED"}'
    http = HttpFixture(body)
    verifier = OpenAISemanticVerifier(api_key="synthetic", model="synthetic-model", opener=http)
    with pytest.raises((ProviderResponseInvalid, PermissionError)):
        verifier.verify(SOURCE, DRAFT if kind != "changed-anchor" else "Factory opened 20 lines.")
    assert len(http.requests) == (0 if kind == "changed-anchor" else 1)


def test_free_semantic_verifier_pins_one_qualified_model_and_never_falls_back_to_unevaluated_model():
    from newsflow.providers.semantic_verifier import FreeOpenRouterSemanticVerifier

    body = reply()
    body["model"] = "a/qualified-model"
    body["choices"][0]["message"]["content"] = json.dumps(assessment())
    http = FreeHttp([body])
    verifier = FreeOpenRouterSemanticVerifier(
        api_key="synthetic", model="a/qualified-model:free", opener=http
    )
    assert assess_semantic_facts(SOURCE, DRAFT, verifier.verify(SOURCE, DRAFT)).eligible is True
    assert len(http.requests) == 1
    request = http.requests[0]
    assert request["model"] == "a/qualified-model:free"
    assert request["provider"]["max_price"] == {"prompt": 0, "completion": 0, "request": 0}
    assert request["provider"]["allow_fallbacks"] is False
    assert verifier.last_usage.provider == "OPENROUTER"


@pytest.mark.parametrize("model", ["openrouter/free", "paid/model"])
def test_semantic_free_router_cannot_use_unidentifiable_or_paid_model(model):
    from newsflow.providers.semantic_verifier import FreeOpenRouterSemanticVerifier

    http = FreeHttp([])
    with pytest.raises(ValueError):
        FreeOpenRouterSemanticVerifier(api_key="synthetic", model=model, opener=http)
    assert http.requests == []
