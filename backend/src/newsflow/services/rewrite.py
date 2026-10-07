"""Rewrite application service."""

from typing import Protocol

from newsflow.domain.editorial import EditorialDecision, editorial_allows_rewrite
from newsflow.services.fact_guard import FactGuard


class TextRewriteProvider(Protocol):
    def rewrite(self, text: str) -> str: ...


class EditorialRewriteBlocked(PermissionError):
    """Raised whenever a non-passing item reaches the rewrite boundary."""


class RewriteService:
    """Second enforcement boundary before a provider call."""

    def __init__(self, provider: TextRewriteProvider) -> None:
        self._provider = provider

    def rewrite(self, source_text: str, decision: EditorialDecision) -> str:
        if not editorial_allows_rewrite(decision):
            raise EditorialRewriteBlocked("EDITORIAL_REWRITE_BLOCKED")
        guard = FactGuard()
        guard.validate_source(source_text)
        rewritten = self._provider.rewrite(source_text)
        guard.require_preserved(source_text, rewritten)
        return rewritten
