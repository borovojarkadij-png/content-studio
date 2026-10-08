"""Explicit encrypted text-sender construction, not runtime opt-in wiring.

Shares the current session/peer decryption and compare-and-swap persistence seam
with the read-only provider. Never generates credentials or logs plaintext.
"""

from newsflow.providers.telegram_publication import TelethonTextPublisher
from newsflow.services.telegram_provider_factory import ConfiguredTelegramProvider


class ConfiguredTelegramTextPublisher(TelethonTextPublisher):
    def __init__(self, session_factory, *, cipher, api_id, api_hash, client_factory=None):
        self._configured = ConfiguredTelegramProvider(
            session_factory,
            cipher=cipher,
            api_id=api_id,
            api_hash=api_hash,
            client_factory=client_factory,
        )
        super().__init__(self._bound_adapter)

    def _bound_adapter(self, envelope):
        # Every publication obtains current encrypted values, with its DB
        # transaction closed before connecting; final runner guard fences changes.
        return self._configured._adapter(
            str(envelope.account_id), str(envelope.telegram_channel_id)
        )
