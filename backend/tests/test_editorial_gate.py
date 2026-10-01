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
