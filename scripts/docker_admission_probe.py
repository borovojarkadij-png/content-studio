"""Create-only synthetic admission restart proof; never execute a provider job."""

import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.persistence import models
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.durable_semantic_runner import DurableSemanticRunner
from newsflow.services.durable_source_photo_runner import DurableSourcePhotoRunner

NAME = "synthetic-admission-v1"
FILE = NAME + ".json"
JOBS_FILE = NAME + "-jobs.json"
KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
CHANNEL = -1001444555000
SOURCE = "Synthetic factory opened 3 lines."
DRAFT = "3 lines opened at the synthetic factory."
NETWORK_FLAGS = (
    "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
    "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
    "NEWSFLOW_REWRITE_ENABLED",
    "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
    "NEWSFLOW_INTERNET_MEDIA_ENABLED",
    "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    "NEWSFLOW_PUBLICATION_ENABLED",
)


def forbidden(*_, **__):
    raise AssertionError("Admission-only probe reached a provider")


def validate(manifest):
    if type(manifest.get("version")) is not int or manifest["version"] != 1:
        raise RuntimeError("Invalid admission manifest version; preserve original history")
    for name in ("account", "donor", "release", "mapping"):
        if type(manifest.get(name)) is not int or manifest[name] <= 0:
            raise RuntimeError("Invalid admission fixture identity")
    for name, size in (
        ("channels", 3),
        ("semantic", 101),
        ("library", 101),
        ("source", 101),
        ("rewrites", 303),
        ("decisions", 101),
    ):
        values = manifest.get(name)
        if (
            not isinstance(values, list)
            or len(values) != size
            or any(type(value) is not int or value <= 0 for value in values)
            or len(set(values)) != size
        ):
            raise RuntimeError("Invalid admission fixture row vector")


def seed(sessions, root, *, now):
    if (root / FILE).exists() or (root / JOBS_FILE).exists():
        raise RuntimeError("Fixture exists; refusing to replace admission history")
    cipher = SessionCipher(KEY)
    with sessions.begin() as session:
        if (
            session.scalar(
                select(models.TelegramAccount.id).where(models.TelegramAccount.name == NAME)
            )
            is not None
        ):
            raise RuntimeError("SQL fixture exists; refusing to replace admission history")
        account = models.TelegramAccount(
            name=NAME,
            telegram_user_id=707707700,
            encrypted_session=cipher.encrypt(NAME),
            health_status="CONNECTED",
        )
        session.add(account)
        session.flush()
        donor = models.DonorChannel(
            telegram_account_id=account.id, telegram_channel_id=CHANNEL, title=NAME
        )
        channels = [
            models.OutputChannel(
                telegram_account_id=account.id,
                telegram_channel_id=CHANNEL - offset,
                title=f"{NAME}:{kind}",
            )
            for offset, kind in enumerate(("semantic", "library", "source"), start=1)
        ]
        release = models.SemanticVerifierReleaseModel(
            provider="OPENAI",
            model=NAME,
            prompt_version="semantic-facts-v1",
            benchmark_version="semantic-facts-v1",
            report_sha256="f" * 64,
            active=True,
        )  # Synthetic only; NOT operational qualification.
        session.add_all([donor, release, *channels])
        session.flush()
        mapping = models.ChannelMappingModel(
            donor_channel_id=donor.id,
            output_channel_id=channels[2].id,
            intake_percent=100,
            target_mix_percent=100,
            media_policy="REUSE_SOURCE",
        )
        session.add_all(
            [
                mapping,
                models.AutomaticApprovalPolicyModel(
                    output_channel_id=channels[0].id, mode="VERIFIED", release_id=release.id
                ),
            ]
        )
        session.flush()
        session.add(
            models.MappingSourceRightsModel(
                mapping_id=mapping.id, license_code="OWNED", attribution="", revision=1
            )
        )
        manifest = {
            "version": 1,
            "account": account.id,
            "donor": donor.id,
            "release": release.id,
            "mapping": mapping.id,
            "channels": [channel.id for channel in channels],
            "semantic": [],
            "library": [],
            "source": [],
            "rewrites": [],
            "decisions": [],
            "session_sha256": sha256(account.encrypted_session.encode()).hexdigest(),
        }
        for number in range(101):
            message = 1000 + number
            key = f"{account.id}:{CHANNEL}:{message}:revision:1"
            post = models.IncomingPostModel(
                telegram_account_id=str(account.id),
                donor_channel_id=str(CHANNEL),
                telegram_message_id=message,
                state="RECEIVED",
            )
            decision = models.EditorialDecisionModel(
                content_key=key,
                status="PASS",
                rewrite_allowed=True,
                sentiment="neutral",
                framing="neutral",
            )
            session.add_all([post, decision])
            session.flush()
            manifest["decisions"].append(decision.id)
            session.add(
                models.ContentRevisionModel(
                    incoming_post_id=post.id,
                    revision_number=1,
                    source_text=SOURCE,
                    media_type="photo",
                    media_id="123",
                    media_protected=False,
                    source_updated_at=now,
                )
            )
            for channel, kind in zip(channels, ("semantic", "library", "source"), strict=True):
                job = models.RewriteJobModel(
                    content_key=key,
                    output_channel_id=channel.id,
                    idempotency_key=f"{NAME}:{kind}:{number}",
                    state="SUCCEEDED",
                )
                session.add(job)
                session.flush()
                output = models.RewriteOutputModel(
                    content_key=key,
                    rewrite_job_id=job.id,
                    output_channel_id=channel.id,
                    rewritten_text=DRAFT,
                    approval_state="PENDING" if kind == "semantic" else "APPROVED",
                )
                candidate = models.PublicationCandidateModel(
                    content_key=key,
                    output_channel_id=channel.id,
                    mapping_id=mapping.id if kind == "source" else None,
                    priority=1,
                    state="AWAITING_REWRITE" if kind == "semantic" else "READY",
                    media_policy="LICENSED_LIBRARY" if kind == "library" else "REUSE_SOURCE",
                )
                session.add_all([output, candidate])
                session.flush()
                manifest[kind].append(output.id if kind == "semantic" else candidate.id)
                manifest["rewrites"].append(job.id)
    # Retain neutral historical drafts before changing old editorial decisions.
    with sessions.begin() as session:
        for row_id in manifest["decisions"][:-1]:
            decision = session.get(models.EditorialDecisionModel, row_id)
            decision.status, decision.rewrite_allowed = "REJECT", False
            decision.sentiment, decision.framing = "negative", "hostile"
            decision.protected_entities = "Украина"
    validate(manifest)
    with (root / FILE).open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream)
    verify(sessions, manifest, admitted=False)
    return manifest


def verify(sessions, manifest, *, admitted, job_ids=()):
    validate(manifest)
    if admitted and (
        not isinstance(job_ids, (tuple, list))
        or len(job_ids) != 3
        or any(type(value) is not int or value <= 0 for value in job_ids)
    ):
        raise RuntimeError("Invalid retained admission job identities")
    with sessions() as session:
        account = session.get(models.TelegramAccount, manifest["account"])
        assert sha256(account.encrypted_session.encode()).hexdigest() == manifest["session_sha256"]
        assert SessionCipher(KEY).decrypt(account.encrypted_session) == NAME
        for index, row_id in enumerate(manifest["decisions"]):
            row = session.get(models.EditorialDecisionModel, row_id)
            assert (row.status, row.rewrite_allowed) == (
                ("PASS", True) if index == 100 else ("REJECT", False)
            )
        rewrites = session.scalars(
            select(models.RewriteJobModel).where(
                models.RewriteJobModel.output_channel_id.in_(manifest["channels"])
            )
        ).all()
        assert sorted(row.id for row in rewrites) == sorted(manifest["rewrites"])
        assert all(row.state == "SUCCEEDED" and row.attempts == 0 for row in rewrites)
        assert (
            session.scalar(
                select(models.RewriteUsageModel.id).where(
                    models.RewriteUsageModel.rewrite_job_id.in_(manifest["rewrites"])
                )
            )
            is None
        )
        semantic = session.scalars(
            select(models.SemanticVerificationJobModel).where(
                models.SemanticVerificationJobModel.rewrite_output_id.in_(manifest["semantic"])
            )
        ).all()
        media = session.scalars(
            select(models.MediaAcquisitionJobModel)
            .where(
                models.MediaAcquisitionJobModel.candidate_id.in_(
                    manifest["library"] + manifest["source"]
                )
            )
            .order_by(models.MediaAcquisitionJobModel.acquisition_mode)
        ).all()
        assert len(semantic) == (1 if admitted else 0) and len(media) == (2 if admitted else 0)
        if not admitted:
            return
        assert tuple([semantic[0].id] + [row.id for row in media]) == tuple(job_ids)
        assert semantic[0].rewrite_output_id == manifest["semantic"][-1]
        assert semantic[0].release_id == manifest["release"] and semantic[0].evidence_id is None
        assert [(row.acquisition_mode, row.candidate_id) for row in media] == [
            ("LICENSED_LIBRARY", manifest["library"][-1]),
            ("REUSE_SOURCE", manifest["source"][-1]),
        ]
        assert all(
            row.state == "QUEUED"
            and row.attempts == 0
            and row.claim_token is None
            and row.lease_expires_at is None
            for row in [*semantic, *media]
        )
        assert all(row.selected_asset_id is None for row in media)
        assert (
            session.scalar(
                select(models.SemanticVerificationUsageModel.id).where(
                    models.SemanticVerificationUsageModel.verification_job_id == semantic[0].id
                )
            )
            is None
        )
        assert (
            session.get(models.RewriteOutputModel, manifest["semantic"][-1]).approval_state
            == "PENDING"
        )


def admit(sessions, root, manifest, *, now):
    validate(manifest)
    operations = (
        DurableSemanticRunner(sessions, verifier_for_release=forbidden),
        DurableMediaRunner(sessions, root, provider=object()),
        DurableSourcePhotoRunner(sessions, root, provider=object()),
    )
    for operation in operations:
        cursor = 0
        for _ in range(7):
            result = operation.enqueue_window(now=now, after_id=cursor)
            assert len(result.scanned_ids) <= 16 and len(result.queued_ids) <= 1
            cursor = result.cursor
        # A repeat after wrap can revisit rejects, never create an extra job.
        assert operation.enqueue_window(now=now, after_id=0).queued_ids == ()
    with sessions() as session:
        semantic = session.scalars(
            select(models.SemanticVerificationJobModel).where(
                models.SemanticVerificationJobModel.rewrite_output_id == manifest["semantic"][-1]
            )
        ).one()
        media = session.scalars(
            select(models.MediaAcquisitionJobModel)
            .where(
                models.MediaAcquisitionJobModel.candidate_id.in_(
                    [manifest["library"][-1], manifest["source"][-1]]
                )
            )
            .order_by(models.MediaAcquisitionJobModel.acquisition_mode)
        ).all()
        job_ids = tuple([semantic.id] + [row.id for row in media])
    verify(sessions, manifest, admitted=True, job_ids=job_ids)
    return job_ids


def main(mode):
    url = os.environ["DATABASE_URL"]
    target = make_url(url)
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or target.database != "newsflow_verification"
        or target.get_backend_name() != "postgresql"
    ):
        raise RuntimeError("Admission probe requires isolated PostgreSQL verification database")
    if mode not in {"seed", "verify-pending", "admit", "verify"}:
        raise ValueError("Unsupported admission mode")
    if any(os.getenv(flag, "0") != "0" for flag in NETWORK_FLAGS):
        raise RuntimeError("Admission probe requires all network workers disabled")
    if load_runtime_master_key() != KEY:
        raise RuntimeError("Unexpected fixture key; never regenerate or replace secrets")
    engine = create_engine(url)
    try:
        sessions, root = sessionmaker(engine), Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
        if mode == "seed":
            seed(sessions, root, now=datetime.now(UTC))
        else:
            manifest = json.loads((root / FILE).read_text(encoding="utf-8"))
            if mode == "admit":
                jobs = admit(sessions, root, manifest, now=datetime.now(UTC))
                with (root / JOBS_FILE).open("x", encoding="utf-8") as stream:
                    json.dump({"version": 1, "jobs": jobs}, stream)
            elif mode == "verify-pending":
                verify(sessions, manifest, admitted=False)
            else:
                retained = json.loads((root / JOBS_FILE).read_text(encoding="utf-8"))
                if type(retained.get("version")) is not int or retained["version"] != 1:
                    raise RuntimeError("Invalid retained admission job manifest")
                verify(sessions, manifest, admitted=True, job_ids=retained["jobs"])
    finally:
        engine.dispose()
    print(f"Synthetic admission {mode}: PASS; no provider execution or publications")


if __name__ == "__main__":
    main(sys.argv[1])
