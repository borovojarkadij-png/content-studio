"""Rewrite application service."""

from typing import Protocol

from newsflow.domain.editorial import EditorialDecision, EditorialStatus


class TextRewriteProvider(Protocol):
    def rewrite(self, text: str) -> str: ...


class EditorialRewriteBlocked(PermissionError):
    """Raised whenever a non-passing item reaches the rewrite boundary."""


class RewriteService:
    """Second enforcement boundary before a provider call."""

    def __init__(self, provider: TextRewriteProvider) -> None:
        self._provider = provider

    def rewrite(self, source_text: str, decision: EditorialDecision) -> str:
        if decision.status is not EditorialStatus.PASS or not decision.rewrite_allowed:
            raise EditorialRewriteBlocked("EDITORIAL_REWRITE_BLOCKED")
        return self._provider.rewrite(source_text)
