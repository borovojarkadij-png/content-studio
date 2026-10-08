"""Create-only synthetic source-photo persistence probe; never live authorization."""

import io
import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from PIL import Image
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence.models import (
    EditorialDecisionModel,
    MappingSourceRightsModel,
    MediaAcquisitionJobModel,
    PublicationCandidateModel,
    RewriteJobModel,
    TelegramAccount,
)
from newsflow.providers.telegram import FakeTelegramProvider, TelegramMessage
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_media_runner import MediaClaim
from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner
from newsflow.services.media_selection import LocalMediaSelectionService, MediaSelectionBlocked
from newsflow.services.rewrite_outputs import RewriteOutputService
from newsflow.services.source_photo import SourcePhotoAcquisition
from newsflow.services.source_revisions import source_revision
from newsflow.services.telegram_configuration import TelegramConfigurationService

NAME = "synthetic-source-photo"
CHANNEL = -1001666555000


def seed_configuration(sessions):
    with sessions() as session:
        if (
            session.scalar(select(TelegramAccount.id).where(TelegramAccount.name == NAME))
            is not None
        ):
            raise RuntimeError("Use a fresh fixture; refusing to replace source photo history")
        config = TelegramConfigurationService(session)
        account = config.create_account(NAME, 600601)
        donor = config.create_donor(account["id"], CHANNEL, NAME)
        output = config.create_output(account["id"], CHANNEL - 1, NAME)
        mapping = config.create_mapping(donor["id"], output["id"], 100, 100)
        config.set_source_media_rights(mapping["id"], "OWNED", "")
        return account, mapping


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


class SyntheticPhotos(FakeTelegramProvider):
    def __init__(self, sessions, candidate_id, event):
        super().__init__()
        self.sessions, self.candidate_id, self.calls = sessions, candidate_id, 0
        self._messages[(event.account_id, event.donor_identifier, event.message_id)] = event
        self._photos[(event.account_id, event.donor_identifier, event.message_id)] = photo()

    def download_photo(self, account_id, donor_identifier, message_id):
        self.calls += 1
        # Inject a separate real PostgreSQL writer during the would-be RPC.
        # Any retained account/candidate/editorial row lock fails this probe.
        with self.sessions.begin() as session:
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            session.scalar(
                select(TelegramAccount)
                .where(TelegramAccount.id == int(account_id))
                .with_for_update()
            )
            candidate = session.scalar(
                select(PublicationCandidateModel)
                .where(PublicationCandidateModel.id == self.candidate_id)
                .with_for_update()
            )
            session.scalar(
                select(EditorialDecisionModel)
                .where(EditorialDecisionModel.content_key == candidate.content_key)
                .with_for_update()
            )
            session.scalars(
                select(MediaAcquisitionJobModel)
                .where(MediaAcquisitionJobModel.candidate_id == self.candidate_id)
                .with_for_update()
            ).all()
            session.get(MappingSourceRightsModel, candidate.mapping_id, with_for_update=True)
        return super().download_photo(account_id, donor_identifier, message_id)


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Source photo probe requires the isolated verification database")
    if mode not in {"seed", "recover", "verify", "blocked"}:
        raise ValueError("Unsupported source photo probe mode")
    engine = create_engine(url)
    sessions = sessionmaker(engine)
    root = Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
    if mode == "seed":
        account, mapping = seed_configuration(sessions)
        with sessions.begin() as session:
            row = session.get(TelegramAccount, account["id"])
            row.encrypted_session = SessionCipher(
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
            ).encrypt("synthetic source photo session")
            row.health_status = "CONNECTED"
        with sessions() as session:
            event = TelegramMessage(
                str(account["id"]),
                str(CHANNEL),
                20,
                "Synthetic photo caption",
                media_type="photo",
                media_id="123",
                media_protected=False,
                source_updated_at=datetime.now(UTC),
            )
            result = DurableIngestionWorkflow(session, configured_mapping_id=mapping["id"]).ingest(
                event, observed_at=datetime.now(UTC), sentiment="neutral", framing="neutral"
            )
            assert result.status == "REWRITE_QUEUED"
        with sessions() as session:
            key = f"{account['id']}:{CHANNEL}:20:revision:1"
            job = session.scalars(
                select(RewriteJobModel).where(RewriteJobModel.content_key == key)
            ).one()
            job.state = "SUCCEEDED"  # Synthetic fixture only; never a real model qualification.
            session.commit()
            review = RewriteOutputService(session)
            draft = review.record_succeeded_output(job.id, "Synthetic photo caption")
            review.approve(draft["id"], activate_candidate=True)
    with sessions() as session:
        account = session.scalars(select(TelegramAccount).where(TelegramAccount.name == NAME)).one()
        key = f"{account.id}:{CHANNEL}:20:revision:1"
        candidate = session.scalars(
            select(PublicationCandidateModel).where(PublicationCandidateModel.content_key == key)
        ).one()
        candidate_id = candidate.id
        revision = source_revision(session, key)
        assert revision.media_id == "123" and revision.media_protected is False
        updated = revision.source_updated_at
        event = TelegramMessage(
            str(account.id),
            str(CHANNEL),
            20,
            revision.source_text,
            media_type="photo",
            media_id="123",
            media_protected=False,
            source_updated_at=updated.replace(tzinfo=UTC) if updated.tzinfo is None else updated,
        )
    provider = SyntheticPhotos(sessions, candidate_id, event)
    operation = SourcePhotoAcquisition(sessions, root, provider=provider)
    execution = DurableSourcePhotoRunner(sessions, root, provider=provider)
    if mode == "seed":
        result = operation.acquire(candidate_id, license_code="OWNED", attribution="")
        assert result["status"] == "ACQUIRED" and not result["illustration"] and provider.calls == 1
        job_id = execution.enqueue_configured(candidate_id, now=datetime.now(UTC))
        assert execution.enqueue_configured(candidate_id, now=datetime.now(UTC)) == job_id
        old = execution.claim_next(now=datetime.now(UTC))
        assert old.job_id == job_id and old.attempt == 1
        with sessions() as session:
            job = session.get(MediaAcquisitionJobModel, job_id)
            assert job.state == "RUNNING" and job.selected_asset_id is None
    elif mode == "recover":
        with sessions() as session:
            job = session.scalars(
                select(MediaAcquisitionJobModel).where(
                    MediaAcquisitionJobModel.candidate_id == candidate_id,
                    MediaAcquisitionJobModel.acquisition_mode == "REUSE_SOURCE",
                )
            ).one()
            assert job.state == "RUNNING" and job.attempts == 1
            old = MediaClaim(job.id, job.claim_token, job.attempts)
        new = execution.claim_next(now=datetime.now(UTC))
        assert (
            new is not None
            and new.job_id == old.job_id
            and new.attempt == 2
            and new.token != old.token
        )
        assert execution.execute(old) == "LOST_LEASE" and provider.calls == 0
        assert execution.execute(new) == "SUCCEEDED" and provider.calls == 1
    elif mode == "blocked":
        with sessions.begin() as session:
            decision = session.scalars(
                select(EditorialDecisionModel).where(EditorialDecisionModel.content_key == key)
            ).one()
            decision.status, decision.rewrite_allowed = "REJECT", False
        try:
            operation.acquire(candidate_id, license_code="OWNED", attribution="")
        except MediaSelectionBlocked:
            pass
        else:
            raise AssertionError("Rejected source photo reached acquisition")
        assert provider.calls == 0
        try:
            with urlopen(
                f"http://api:8000/api/telegram/publication-candidates/{candidate_id}/media-selection?query=photo",
                timeout=15,
            ):
                raise AssertionError("Rejected source photo remained selectable")
        except HTTPError as error:
            assert error.code == 409
        with urlopen(
            f"http://api:8000/api/telegram/publication-candidates/{candidate_id}/media-acquisition",
            timeout=15,
        ) as response:
            status = json.load(response)
            assert (
                status["state"] == "SUCCEEDED"
                and status["selected_allowed"] is False
                and status["asset"] is None
            )
    if mode == "verify":
        with sessions() as session:
            job = session.scalars(
                select(MediaAcquisitionJobModel).where(
                    MediaAcquisitionJobModel.candidate_id == candidate_id,
                    MediaAcquisitionJobModel.acquisition_mode == "REUSE_SOURCE",
                )
            ).one()
            assert (
                job.state == "SUCCEEDED" and job.attempts == 2 and job.selected_asset_id is not None
            )
            rights = session.get(MappingSourceRightsModel, candidate.mapping_id)
            assert rights.license_code == "OWNED" and rights.revision == 1
        with urlopen(
            f"http://api:8000/api/telegram/publication-candidates/{candidate_id}/media-acquisition",
            timeout=15,
        ) as response:
            status = json.load(response)
            assert status["selected_allowed"] is True and status["illustration"] is False
            assert status["asset"]["origin"] == "SOURCE"
    if mode != "blocked":
        with sessions() as session:
            selected = LocalMediaSelectionService(session, root).select_for_candidate(
                candidate_id, query="photo"
            )
            asset = selected["items"][0]
            assert selected["status"] == "SELECTED" and asset["source_content_key"] == key
            assert (
                asset["license_code"] == "OWNED" and asset["sha256"] == sha256(photo()).hexdigest()
            )
            assert (root / asset["storage_key"]).read_bytes() == photo()
    engine.dispose()
    print(
        f"Synthetic source photo {mode} PASS; exact persistent bytes/rights/identity; external calls=0; sends=0"
    )


if __name__ == "__main__":
    main(sys.argv[1])
