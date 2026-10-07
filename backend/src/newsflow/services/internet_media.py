"""Guarded free photo acquisition into existing durable licensed library.

This seam does not publish, approve drafts or assert an illustration is a real
event photograph. Durable acquisition jobs/UI wiring are separate increments.
"""

import os
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import select

from newsflow.domain.editorial import editorial_allows_rewrite
from newsflow.persistence.models import (
    EditorialDecisionModel,
    PublicationCandidateModel,
    RewriteJobModel,
    RewriteOutputModel,
)
from newsflow.providers.commons_images import CommonsImageProvider, search_terms
from newsflow.services.automatic_approval import approval_is_current
from newsflow.services.media_selection import (
    LocalMediaSelectionService,
    MediaSelectionBlocked,
    MediaUnavailable,
)
from newsflow.services.semantic_facts import text_digest
from newsflow.services.source_revisions import revision_is_latest, source_revision


class InternetMediaAcquisition:
    def __init__(self, session_factory, media_root: Path, *, provider=None):
        self._factory, self._root = session_factory, media_root.resolve(strict=True)
        self._provider = provider or CommonsImageProvider()
        if not self._root.is_dir():
            raise MediaUnavailable("Persistent media root is unavailable")

    @staticmethod
    def _binding(session, candidate_id):
        # Resolve identifiers first; shared lock order: job -> editorial -> draft
        # -> approval policy/release -> candidate. No locks over network I/O.
        identity = session.execute(
            select(
                PublicationCandidateModel.content_key, PublicationCandidateModel.output_channel_id
            ).where(PublicationCandidateModel.id == candidate_id)
        ).one_or_none()
        if identity is None:
            raise LookupError("Publication candidate was not found")
        key, channel_id = identity
        output_job_id = session.scalar(
            select(RewriteOutputModel.rewrite_job_id).where(
                RewriteOutputModel.content_key == key,
                RewriteOutputModel.output_channel_id == channel_id,
            )
        )
        job = session.scalar(
            select(RewriteJobModel)
            .where(RewriteJobModel.id == output_job_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        decision = session.scalar(
            select(EditorialDecisionModel)
            .where(EditorialDecisionModel.content_key == key)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if job is None or not editorial_allows_rewrite(decision):
            raise MediaSelectionBlocked("EDITORIAL_OR_REWRITE_GUARD_BLOCKED")
        source = source_revision(session, key)
        if source is None or not revision_is_latest(session, source):
            raise MediaSelectionBlocked("SOURCE_REVISION_NOT_CURRENT_OR_MISSING")
        output = session.scalar(
            select(RewriteOutputModel)
            .where(RewriteOutputModel.rewrite_job_id == job.id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if output is None or not approval_is_current(session, output):
            raise MediaSelectionBlocked("CURRENT_APPROVAL_REQUIRED")
        candidate = session.scalar(
            select(PublicationCandidateModel)
            .where(PublicationCandidateModel.id == candidate_id)
            .execution_options(populate_existing=True)
            .with_for_update()
        )
        if (
            candidate is None
            or candidate.content_key != key
            or candidate.output_channel_id != channel_id
            or candidate.state not in {"READY", "SCHEDULED"}
            or candidate.media_policy != "LICENSED_LIBRARY"
        ):
            raise MediaSelectionBlocked("INTERNET_MEDIA_POLICY_NOT_ELIGIBLE")
        return (
            key,
            source.id,
            text_digest(source.source_text),
            output.id,
            text_digest(output.rewritten_text),
            source.source_text,
        )

    def _persist(self, content, attribution, mime):
        directory = self._root / "internet"
        directory.mkdir(exist_ok=True)
        if directory.is_symlink() or directory.resolve(strict=True) != directory:
            raise MediaUnavailable("Internet media directory must not be a link")
        extension = ".png" if mime == "image/png" else ".jpg"
        # Provider title/path never becomes a local filename. Rights binding is
        # part of the key so identical bytes cannot silently replace provenance.
        name = text_digest(attribution) + "-" + sha256(content).hexdigest() + extension
        destination = directory / name
        with NamedTemporaryFile(
            dir=directory, prefix="acquire-", suffix=".tmp", delete=False
        ) as staged:
            temporary = Path(staged.name)
            staged.write(content)
            staged.flush()
            os.fsync(staged.fileno())
        try:
            try:
                os.link(temporary, destination)  # atomic create-only, never overwrite an asset
            except FileExistsError:
                if destination.is_symlink() or destination.resolve() != destination:
                    raise MediaUnavailable("Internet media target must not be a link") from None
                with destination.open("rb") as stream:
                    existing = stream.read(16 * 1024 * 1024 + 1)
                if existing != content:
                    raise MediaUnavailable("Internet media identity conflict") from None
        finally:
            temporary.unlink()  # Only this invocation's validated staging file.
        return "internet/" + name

    def acquire(
        self, candidate_id: int, *, execution_guard=None, completion=None
    ) -> dict[str, object]:
        with self._factory() as session:
            if execution_guard:
                execution_guard(session)
            binding = self._binding(session, candidate_id)
        # Free remote topic retrieval; first eligible metadata only, no paid fallback.
        query = search_terms(binding[-1])
        results = self._provider.search(query, limit=5)
        if not results:
            with self._factory() as session:
                if execution_guard:
                    execution_guard(session)
                if self._binding(session, candidate_id) != binding:
                    raise MediaSelectionBlocked("MEDIA_BINDING_CHANGED")
                if completion:
                    completion(session, None)
                session.commit()
            return {"status": "NO_MATCH", "items": [], "illustration": True}
        result = results[0]
        content = self._provider.download(result)
        with self._factory() as session:
            if execution_guard:
                execution_guard(session)
            if self._binding(session, candidate_id) != binding:
                raise MediaSelectionBlocked("MEDIA_BINDING_CHANGED")
            key = self._persist(content, result.attribution, result.mime_type)
            asset = LocalMediaSelectionService(session, self._root).register_asset(
                key,
                origin="LICENSED_LIBRARY",
                license_code=result.license_code,
                attribution=result.attribution,
                tags=tuple(sorted(set(result.tags + tuple(query.split())))),
                commit=False,
            )
            if completion:
                completion(session, asset["id"])
            session.commit()
        return {"status": "ACQUIRED", "items": [asset], "illustration": True}
