"""Bounded read-only Telegram counts, separate from mutable content/media identity."""

from datetime import datetime
from typing import Protocol

from newsflow.domain.engagement import (
    TelegramEngagementObservation,
    validate_engagement_counter,
    validate_engagement_request,
)
from newsflow.providers.telegram import SessionUnavailable


class TelegramEngagementProvider(Protocol):
    def fetch_engagement(
        self, account_id: str, donor_identifier: str, message_id: int, *, observed_at: datetime
    ) -> TelegramEngagementObservation: ...


class FakeTelegramEngagementProvider:
    def __init__(self):
        self._observations = {}

    def seed_observation(self, observation: TelegramEngagementObservation) -> None:
        if not isinstance(observation, TelegramEngagementObservation):
            raise TypeError("Fake requires a validated engagement observation")
        key = (
            observation.account_id,
            observation.donor_identifier,
            observation.message_id,
            observation.observed_at,
        )
        if key in self._observations and self._observations[key] != observation:
            raise ValueError("Conflicting explicit fake engagement observation")
        self._observations[key] = observation

    def fetch_engagement(self, account_id, donor_identifier, message_id, *, observed_at):
        observed_at = validate_engagement_request(
            account_id, donor_identifier, message_id, observed_at
        )
        return self._observations[(account_id, donor_identifier, message_id, observed_at)]


def _reaction_total(aggregate):
    from telethon.tl.types import MessageReactions, ReactionCount

    if aggregate is None:
        return None
    if not isinstance(aggregate, MessageReactions) or (
        aggregate.min is not None and type(aggregate.min) is not bool
    ):
        raise ValueError("Malformed Telegram reaction aggregate")
    if aggregate.min is True:
        return None
    results = aggregate.results
    if not isinstance(results, (list, tuple)) or len(results) > 100:
        raise ValueError("Malformed or unbounded Telegram reaction aggregate")
    total = 0
    for result in results:
        if not isinstance(result, ReactionCount) or result.count is None:
            raise ValueError("Malformed Telegram reaction count")
        total += validate_engagement_counter(result.count)
        validate_engagement_counter(total)
    return total


def read_engagement(provider, account_id, donor_identifier, message_id, *, observed_at):
    observed_at = validate_engagement_request(account_id, donor_identifier, message_id, observed_at)
    if type(provider._expected_user_id) is not int or not 0 < provider._expected_user_id < 2**63:
        raise SessionUnavailable("Engagement requires a provisioned Telegram user identity")

    async def read(client):
        channel = provider._channel_id(donor_identifier)
        peer = await provider._input_channel(client, account_id, channel)
        raw = await client.get_messages(peer, ids=message_id)
        if raw is None:
            raise LookupError("Telegram engagement source no longer exists")
        if (
            type(getattr(raw, "chat_id", None)) is not int
            or raw.chat_id != channel
            or type(getattr(raw, "id", None)) is not int
            or raw.id != message_id
        ):
            raise ValueError("Telegram engagement source identity mismatch")
        return TelegramEngagementObservation(
            account_id,
            donor_identifier,
            message_id,
            getattr(raw, "date", None),
            observed_at,
            getattr(raw, "views", None),
            getattr(raw, "forwards", None),
            _reaction_total(getattr(raw, "reactions", None)),
        )

    return provider._run(account_id, read)
