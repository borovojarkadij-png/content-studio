import pytest

from newsflow.domain import editorial


def test_editorial_gate_exposes_a_reject_decision_with_rewrite_disabled() -> None:
    gate = editorial.EditorialGate()

    decision = gate.evaluate(
        text="Hostile claim about a protected person",
        protected_entities=["Vladimir Putin"],
        sentiment="negative",
        framing="hostile",
    )

    assert decision.status is editorial.EditorialStatus.REJECT
    assert decision.rewrite_allowed is False


@pytest.mark.parametrize(
    "sentiment,framing",
    [("unknown", "neutral"), ("neutral", "unknown"), ("", ""), ("positive", "invented")],
)
def test_unknown_classification_never_allows_rewrite(sentiment, framing):
    decision = editorial.EditorialGate().evaluate(
        text="Unclassified source", protected_entities=(), sentiment=sentiment, framing=framing
    )
    assert decision.status is editorial.EditorialStatus.MANUAL_REVIEW
    assert decision.rewrite_allowed is False
