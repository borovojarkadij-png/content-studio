import pytest

from newsflow.domain.editorial import EditorialDecision, EditorialStatus
from newsflow.services import rewrite


def test_rewrite_service_is_available_as_the_second_editorial_defence() -> None:
    assert hasattr(rewrite, "RewriteService")


class RecordingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def rewrite(self, text: str) -> str:
        self.calls += 1
        return f"rewritten: {text}"


def test_rewrite_service_blocks_a_rejected_item_without_calling_the_provider() -> None:
    provider = RecordingProvider()
    decision = EditorialDecision(
        status=EditorialStatus.REJECT,
        rewrite_allowed=False,
        reason_codes=("PROTECTED_ENTITY_NEGATIVE",),
        protected_entities=("Russia",),
        sentiment="negative",
        framing="hostile",
    )

    with pytest.raises(rewrite.EditorialRewriteBlocked):
        rewrite.RewriteService(provider).rewrite("Rejected source", decision)

    assert provider.calls == 0
