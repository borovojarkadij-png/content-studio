"""Bounded private canonical presentation and validator-bound decoded photo."""

import json
from dataclasses import asdict
from hashlib import sha256

from sqlalchemy import select

from newsflow.persistence.models import (
    ContentRevisionModel,
    IllustrationReviewRecordModel,
    MediaAssetModel,
    OutputChannel,
    PublicationCandidateModel,
    RewriteOutputModel,
)
from newsflow.services.illustration_binding import IllustrationBindingResolver
from newsflow.services.illustration_review import IllustrationReviewWriter
from newsflow.services.media_selection import LocalMediaSelectionService
from newsflow.services.semantic_facts import text_digest


class IllustrationPresentation:
    def __init__(self, session, media_root):
        self._session, self._root = session, media_root

    def latest(self, candidate_id):
        if type(candidate_id) is not int or not 0 < candidate_id <= 2**63 - 1:
            raise ValueError("Positive candidate required")
        if self._session.new or self._session.dirty or self._session.deleted:
            raise ValueError("Clean presentation session required")
        if self._session.get(PublicationCandidateModel, candidate_id) is None:
            raise LookupError("Candidate not found")
        row = self._session.scalar(
            select(IllustrationReviewRecordModel)
            .where(
                IllustrationReviewRecordModel.candidate_id == candidate_id,
                IllustrationReviewRecordModel.record_kind == "REVIEW",
            )
            .order_by(IllustrationReviewRecordModel.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return IllustrationReviewWriter(self._session, self._root)._response(row) if row else None

    def _current(self, candidate_id):
        resolver = IllustrationBindingResolver(self._session, self._root)
        binding = resolver.resolve(candidate_id)
        session = self._session
        source = session.get(
            ContentRevisionModel, binding.source_revision_id, populate_existing=True
        )
        draft = session.get(RewriteOutputModel, binding.rewrite_output_id, populate_existing=True)
        asset = session.get(MediaAssetModel, binding.media_asset_id, populate_existing=True)
        channel = session.get(OutputChannel, binding.output_channel_id, populate_existing=True)
        if (
            source is None
            or draft is None
            or asset is None
            or channel is None
            or len(source.source_text.encode("utf-8")) > 262144
            or len(draft.rewritten_text.encode("utf-8")) > 262144
            or len(channel.title) > 255
            or text_digest(source.source_text) != binding.source_sha256
            or text_digest(draft.rewritten_text) != binding.draft_sha256
        ):
            raise PermissionError("Canonical presentation changed")
        value = {
            "binding": asdict(binding),
            "source_text": source.source_text,
            "draft_text": draft.rewritten_text,
            "channel": {
                "id": channel.id,
                "title": channel.title,
                "telegram_channel_id": str(channel.telegram_channel_id),
            },
            "license_code": asset.license_code,
            "attribution": asset.attribution,
            "mime_type": asset.mime_type,
        }
        if resolver.resolve(candidate_id) != binding:
            raise PermissionError("Canonical presentation changed")
        return value, asset.storage_key

    @staticmethod
    def validator(value):
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return '"' + sha256(encoded).hexdigest() + '"'

    def presentation(self, candidate_id):
        first, _ = self._current(candidate_id)
        first["latest_review"] = self.latest(candidate_id)
        after, _ = self._current(candidate_id)
        after["latest_review"] = self.latest(candidate_id)
        if first != after:
            raise PermissionError("Canonical presentation changed")
        return first, self.validator(first)

    def photo(self, candidate_id, validator):
        first, key = self._current(candidate_id)
        first["latest_review"] = self.latest(candidate_id)
        etag = self.validator(first)
        if validator != etag:
            raise PermissionError("Matching presentation validator required")
        content, digest, mime = LocalMediaSelectionService(
            self._session, self._root
        )._photo_content(key)
        after, after_key = self._current(candidate_id)
        after["latest_review"] = self.latest(candidate_id)
        if (
            first != after
            or key != after_key
            or digest != first["binding"]["media_sha256"]
            or mime != first["mime_type"]
        ):
            raise PermissionError("Canonical preview changed")
        return content, mime, etag
