"""Versioned synthetic fact-anchor benchmark; no network/provider credentials."""

import pytest

from newsflow.domain.editorial import EditorialDecision, EditorialStatus
from newsflow.services.rewrite import RewriteService


@pytest.mark.parametrize(
    ("source", "rewritten", "reason"),
    [
        ("Цена 120 рублей", "Цена 150 рублей", "NUMERIC_FACTS_CHANGED"),
        ("Встреча 07.10.2026 в 14:30", "Встреча 08.10.2026 в 14:30", "NUMERIC_FACTS_CHANGED"),
        ("Изменение -5%", "Изменение 5%", "NUMERIC_FACTS_CHANGED"),
        ("Счёт 2:1", "Счёт 2:1; присутствовали 500 человек", "NUMERIC_FACTS_CHANGED"),
        ("Один показатель: 5", "Оба показателя: 5 и 5", "NUMERIC_FACTS_CHANGED"),
        (
            "Источник https://example.org/news?id=1",
            "Источник https://other.org/news?id=1",
            "LINKS_CHANGED",
        ),
        ("Контакт @source_channel", "Контакт @another_channel", "MENTIONS_CHANGED"),
        (
            "Спикер: «Это проверенные сведения»",
            "Спикер: «Это подтверждённый рекорд»",
            "QUOTES_CHANGED",
        ),
        ("Текст", " ", "EMPTY_REWRITE"),
        ("Текст", "x" * 32001, "TEXT_LIMIT_EXCEEDED"),
    ],
)
def test_fact_guard_rejects_changed_removed_or_invented_anchors(source, rewritten, reason):
    from newsflow.services.fact_guard import FactGuard

    report = FactGuard().check(source, rewritten)
    assert report.anchors_preserved is False
    assert reason in report.reason_codes
    assert report.requires_manual_review is True


def test_preserved_anchors_allow_a_draft_but_not_semantic_auto_approval():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check(
        "В Минске 12 команд. Источник https://example.org/news. Контакт @source_channel",
        "12 команд — участники встречи в Минске. Контакт @source_channel; https://example.org/news",
        required_literals=("Минске",),
    )
    assert result.anchors_preserved is True
    assert result.reason_codes == ()
    assert result.requires_manual_review is True


def test_missing_named_fact_is_blocked_even_with_preserved_numbers():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check(
        "Компания Альфа представила 2 проекта",
        "Представлено 2 проекта",
        required_literals=("Компания Альфа",),
    )
    assert result.reason_codes == ("REQUIRED_LITERAL_MISSING",)


class SyntheticProvider:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def rewrite(self, text):
        self.calls += 1
        return self.result


def decision(status=EditorialStatus.PASS, allowed=True):
    return EditorialDecision(status, allowed, (), (), "neutral", "neutral")


def test_rewrite_boundary_checks_facts_and_does_not_retry_changed_facts():
    provider = SyntheticProvider("Открыто 20 объектов")
    with pytest.raises(PermissionError, match="FACT_PRESERVATION_BLOCKED"):
        RewriteService(provider).rewrite("Открыто 10 объектов", decision())
    assert provider.calls == 1


def test_rewrite_boundary_rejects_empty_source_before_any_provider_call():
    provider = SyntheticProvider("invented")
    with pytest.raises(ValueError, match="Source text"):
        RewriteService(provider).rewrite(" ", decision())
    assert provider.calls == 0


@pytest.mark.parametrize(
    "status,allowed",
    [
        (EditorialStatus.REJECT, False),
        (EditorialStatus.MANUAL_REVIEW, False),
        (EditorialStatus.PASS, False),
    ],
)
def test_reject_pending_and_disabled_still_never_reach_fact_or_rewrite_provider(status, allowed):
    provider = SyntheticProvider("irrelevant")
    with pytest.raises(PermissionError, match="EDITORIAL_REWRITE_BLOCKED"):
        RewriteService(provider).rewrite(" ", decision(status, allowed))
    assert provider.calls == 0


def test_fact_guard_never_treats_unchanged_anchors_as_proof_of_semantics():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check("Завод закрыл 3 линии", "Завод открыл 3 линии")
    assert result.anchors_preserved is True
    assert result.requires_manual_review is True


def test_long_source_is_refused_before_a_provider_call():
    provider = SyntheticProvider("unused")
    with pytest.raises(ValueError, match="Source text exceeds"):
        RewriteService(provider).rewrite("x" * 32001, decision())
    assert provider.calls == 0


def test_literal_substring_is_not_a_preserved_named_fact():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check("Компания Альфа", "Компания Альфабет", required_literals=("Альфа",))
    assert result.anchors_preserved is False


def test_non_text_provider_output_is_rejected_without_leaking_it():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check("Исходный текст", {"secret": "synthetic"})
    assert result.reason_codes == ("EMPTY_REWRITE",)


def test_unicode_digit_format_preserves_the_same_numeric_anchor():
    from newsflow.services.fact_guard import FactGuard

    result = FactGuard().check("Встреча: １２ участников", "Участников встречи: 12")
    assert result.anchors_preserved is True


def test_fact_literal_must_be_evidence_from_the_source_not_an_injected_claim():
    from newsflow.services.fact_guard import FactGuard

    with pytest.raises(ValueError, match="not present in the source"):
        FactGuard().check("Источник", "Источник", required_literals=("invented",))


def test_inconsistent_pass_flag_cannot_override_protected_entity_hard_constraints():
    provider = SyntheticProvider("unsafe")
    forged_pass = EditorialDecision(
        EditorialStatus.PASS, True, (), ("Protected",), "negative", "hostile"
    )
    with pytest.raises(PermissionError, match="EDITORIAL_REWRITE_BLOCKED"):
        RewriteService(provider).rewrite("Negative protected claim", forged_pass)
    assert provider.calls == 0


def test_publication_also_rechecks_protected_hard_constraints_despite_pass_flag():
    from datetime import UTC, datetime, timedelta

    from newsflow.services.publication import PublicationService

    class Publisher:
        calls = 0

        def publish(self, text):
            self.calls += 1
            return "unsafe"

    publisher = Publisher()
    now = datetime.now(UTC)
    forged_pass = EditorialDecision(
        EditorialStatus.PASS, True, (), ("Protected",), "negative", "hostile"
    )
    with pytest.raises(PermissionError, match="PUBLICATION_HARD"):
        PublicationService(publisher).publish(
            text="unsafe",
            decision=forged_pass,
            expires_at=now + timedelta(hours=1),
            scheduled_for=now,
            is_cancelled=False,
            idempotency_key="synthetic-forged-policy",
        )
    assert publisher.calls == 0
