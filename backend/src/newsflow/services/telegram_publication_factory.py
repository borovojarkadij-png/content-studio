"""Explicit encrypted text/photo-sender construction, not runtime opt-in wiring.

Shares the current session/peer decryption and compare-and-swap persistence seam
with the read-only provider. Never generates credentials or logs plaintext.
"""

from newsflow.providers.telegram_publication import TelethonPhotoPublisher, TelethonTextPublisher
from newsflow.services.media_job_read import MediaJobReader
from newsflow.services.publication import PublicationBlocked
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


class ConfiguredTelegramPhotoPublisher(TelethonPhotoPublisher):
    def __init__(
        self, session_factory, media_root, *, cipher, api_id, api_hash, client_factory=None
    ):
        self._sessions, self._root = session_factory, media_root
        self._configured = ConfiguredTelegramProvider(
            session_factory,
            cipher=cipher,
            api_id=api_id,
            api_hash=api_hash,
            client_factory=client_factory,
        )
        super().__init__(self._bound_adapter, photo_for_envelope=self._bound_photo)

    _bound_adapter = ConfiguredTelegramTextPublisher._bound_adapter

    def _bound_photo(self, envelope):
        # Current completed acquisition, rights, editorial/review/source and
        # bounded decode/hash checks, including a second fresh read after bytes.
        # Return immutable bytes only after closing the database transaction.
        with self._sessions() as session:
            reader = MediaJobReader(session, self._root)
            status = reader.get_status(envelope.candidate_id)
            asset = status["asset"]
            if (
                not status["selected_allowed"]
                or status["illustration"]
                or asset is None
                or asset["id"] != envelope.media_asset_id
                or asset["sha256"] != envelope.media_sha256
                or asset["origin"] != "SOURCE"
                or asset["source_content_key"] != envelope.content_key
            ):
                raise PublicationBlocked("CURRENT_BOUND_SOURCE_PHOTO_REQUIRED")
            content, _ = reader.preview(envelope.candidate_id)
            return content
