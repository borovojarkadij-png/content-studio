"""Contract/parser evals, NOT evidence that a live model classifies correctly."""

import json
from pathlib import Path

import pytest

BENCHMARK = json.loads(
    (Path(__file__).parent / "fixtures/semantic-facts-v1.json").read_text(encoding="utf-8")
)


def payload(source, draft, relation="SUPPORTED", verdict="PRESERVED"):
    return {
        "verdict": verdict,
        "source_complete": True,
        "draft_complete": True,
        "claims": [{"source_quote": source, "draft_quote": draft, "relation": relation}],
    }


@pytest.mark.parametrize("case", BENCHMARK["cases"], ids=lambda case: case["id"])
def test_versioned_semantic_contract_preserves_negative_verdicts(case):
    from newsflow.services.semantic_facts import assess_semantic_facts

    result = assess_semantic_facts(
        case["source"],
        case["draft"],
        payload(case["source"], case["draft"], case["relation"], case["verdict"]),
    )
    assert result.verdict == case["verdict"]
    assert result.eligible is (case["verdict"] == "PRESERVED")


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "unsupported-pass",
        "incomplete",
        "extra",
        "invented-quote",
        "omitted-source",
        "omitted-draft",
        "bad-type",
        "huge",
    ],
)
def test_inconsistent_or_incomplete_semantic_evidence_never_allows_automatic_approval(mutation):
    from newsflow.services.semantic_facts import assess_semantic_facts

    source, draft = "Открыта библиотека. Мост закрыт.", "Библиотека открыта. Мост закрыт."
    value = payload(source, draft)
    if mutation == "empty":
        value["claims"] = []
    elif mutation == "unsupported-pass":
        value["claims"][0]["relation"] = "UNSUPPORTED"
    elif mutation == "incomplete":
        value["source_complete"] = False
    elif mutation == "extra":
        value["publish_now"] = True
    elif mutation == "invented-quote":
        value["claims"][0]["source_quote"] = "Отсутствующая цитата"
    elif mutation == "omitted-source":
        value["claims"][0]["source_quote"] = "Открыта библиотека."
    elif mutation == "omitted-draft":
        value["claims"][0]["draft_quote"] = "Библиотека открыта."
    elif mutation == "bad-type":
        value["source_complete"] = "true"
    elif mutation == "huge":
        value["claims"][0]["source_quote"] = "x" * 32001
    result = assess_semantic_facts(source, draft, value)
    assert result.eligible is False
    assert result.verdict in {"CHANGED", "UNCERTAIN", "ERROR"}


def test_omitted_fact_and_numeric_change_cannot_be_repaired_by_a_pass_verdict():
    from newsflow.services.semantic_facts import assess_semantic_facts

    value = payload("Открыто 10 школ.", "Открыто 20 школ.")
    result = assess_semantic_facts("Открыто 10 школ.", "Открыто 20 школ.", value)
    assert result.eligible is False
    assert "NUMERIC_FACTS_CHANGED" in result.reason_codes
    omitted = payload("Открыта библиотека.", "", "OMITTED", "CHANGED")
    omitted["claims"].append(
        {"source_quote": "Мост закрыт.", "draft_quote": "Мост закрыт.", "relation": "SUPPORTED"}
    )
    result = assess_semantic_facts("Открыта библиотека. Мост закрыт.", "Мост закрыт.", omitted)
    assert result.verdict == "CHANGED"


def test_parser_does_not_echo_untrusted_provider_secrets():
    from newsflow.services.semantic_facts import assess_semantic_facts

    result = assess_semantic_facts("Источник", "Рерайт", {"secret": "synthetic-private-key"})
    assert result.verdict == "ERROR"
    assert "synthetic-private-key" not in repr(result)
