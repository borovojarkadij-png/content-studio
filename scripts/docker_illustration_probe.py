"""Standalone packaged synthetic authenticated workflow; no test-package imports/live clients."""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
from newsflow.persistence import models
from newsflow.providers.commons_images import ImageSearchResult
from newsflow.providers.telegram import TelegramMessage
from newsflow.security.master_key import load_runtime_master_key
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.durable_media_runner import DurableMediaRunner
from newsflow.services.durable_publication_runner import DurablePublicationRunner
from newsflow.services.publication_request_snapshot import (
    PublicationRequestSnapshots,
    _unique_object,
)
from newsflow.services.rewrite_outputs import RewriteOutputService
from newsflow.services.telegram_configuration import TelegramConfigurationService
from newsflow.services.telegram_publication_factory import (
    ConfiguredTelegramPhotoPublisher,
)
from PIL import Image
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from telethon.tl.functions.messages import SendMediaRequest
from telethon.tl.types import (
    Channel,
    ChatAdminRights,
    ChatPhotoEmpty,
    InputFile,
    Message,
    MessageMediaPhoto,
    PeerChannel,
    Photo,
    UpdateMessageID,
    UpdateNewChannelMessage,
    Updates,
)

URL = "postgresql+psycopg://newsflow_fixture:synthetic-illustration-ci-only@postgres:5432/newsflow_illustration_ci"
MASTER = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
TOKEN = "synthetic-illustration-restart-review-token-0001"
OWNER = "content-studio-illustration-v1"
FILE = "illustration-original.json"
KINDS = ("approved", "revoked", "stale", "sending")
SOURCE, DRAFT = "Завод открыл 3 линии.", "Открыты 3 линии на заводе."
FLAGS = (
    "NEWSFLOW_TELEGRAM_CHANNEL_SYNC_ENABLED",
    "NEWSFLOW_TELEGRAM_INGESTION_ENABLED",
    "NEWSFLOW_REWRITE_ENABLED",
    "NEWSFLOW_SEMANTIC_VERIFICATION_ENABLED",
    "NEWSFLOW_INTERNET_MEDIA_ENABLED",
    "NEWSFLOW_SOURCE_PHOTO_ENABLED",
    "NEWSFLOW_PUBLICATION_ENABLED",
)


def digest(value):
    return sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def row_hash(row):
    values = {
        column.name: str(getattr(row, column.name)) for column in row.__table__.columns
    }
    return digest(json.dumps(values, sort_keys=True))


def validate_manifest(value):
    fields = {
        "version",
        "owner",
        "created_at",
        "account",
        "account_hash",
        "peer",
        "peer_hash",
        "cases",
        "rewrites",
        "rejected_decision",
    }
    if (
        type(value) is not dict
        or set(value) != fields
        or type(value["version"]) is not int
        or value["version"] != 1
        or value["owner"] != OWNER
        or type(value["cases"]) is not dict
        or set(value["cases"]) != set(KINDS)
    ):
        raise ValueError("Invalid original illustration manifest")
    for key in ("account", "rejected_decision"):
        if type(value[key]) is not int or value[key] <= 0:
            raise ValueError("Invalid original row identity")
    if (
        type(value["peer"]) is not list
        or value["peer"] != [value["account"], -1001234567891]
        or any(type(i) is not int for i in value["peer"])
    ):
        raise ValueError("Invalid original peer identity")
    if (
        type(value["rewrites"]) is not list
        or len(value["rewrites"]) != 4
        or any(type(i) is not int or i <= 0 for i in value["rewrites"])
    ):
        raise ValueError("Invalid original rewrite identities")
    case_fields = {
        "candidate",
        "planned",
        "job",
        "review",
        "audit",
        "asset",
        "decision",
        "binding",
        "review_hash",
        "audit_hash",
        "snapshot_hash",
        "photo_hash",
        "etag",
        "request_nonce",
    }
    for case in value["cases"].values():
        if type(case) is not dict or set(case) != case_fields:
            raise ValueError("Invalid original case manifest")
        for key in (
            "candidate",
            "planned",
            "job",
            "review",
            "audit",
            "asset",
            "decision",
            "request_nonce",
        ):
            if type(case[key]) is not int or not 0 < case[key] < 2**63:
                raise ValueError("Invalid original case identity")
        for key in ("review_hash", "audit_hash", "snapshot_hash", "photo_hash"):
            if (
                type(case[key]) is not str
                or len(case[key]) != 64
                or any(c not in "0123456789abcdef" for c in case[key])
            ):
                raise ValueError("Invalid retained hash")
    datetime.fromisoformat(value["created_at"])


def write_new(root, filename, value):
    with (root / filename).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)


def read_manifest(path):
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("Retained manifest redirected or oversized")
    return json.loads(path.read_text(), object_pairs_hook=_unique_object)


def validate_aux(value, *, result=False):
    fields = (
        {
            "version",
            "approved_fake_calls",
            "revoked_stale_sending_calls",
            "rewrite_calls",
            "nonce",
            "observation_hash",
        }
        if result
        else {"version", "revocation", "revocation_hash", "audit", "audit_hash"}
    )
    if (
        type(value) is not dict
        or set(value) != fields
        or type(value["version"]) is not int
        or value["version"] != 1
    ):
        raise ValueError("Invalid retained auxiliary manifest")
    for key, item in value.items():
        if key.endswith("_hash"):
            if (
                type(item) is not str
                or len(item) != 64
                or any(c not in "0123456789abcdef" for c in item)
            ):
                raise ValueError("Invalid retained hash")
        elif type(item) is not int or item < 0 or item >= 2**63:
            raise ValueError("Invalid retained integer")


def result_manifest(sessions, manifest):
    with sessions() as session:
        observation = session.get(
            models.PublicationDeliveryObservationModel,
            manifest["cases"]["approved"]["job"],
        )
        assert observation is not None
        return {
            "version": 1,
            "approved_fake_calls": 1,
            "revoked_stale_sending_calls": 0,
            "rewrite_calls": 0,
            "nonce": manifest["cases"]["approved"]["request_nonce"],
            "observation_hash": row_hash(observation),
        }


def http(path, *, payload=None, headers=None, authorized=True, status=200):
    merged = {"Authorization": "Bearer " + TOKEN} if authorized else {}
    merged.update(headers or {})
    if payload is not None:
        merged["Content-Type"] = "application/json"
    request = Request(
        "http://api:8000" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=merged,
    )
    try:
        response = urlopen(request, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        assert response.status == status, (
            f"HTTP expected {status}, received {response.status}"
        )
        raw = response.read(262145)
        assert len(raw) <= 262144
        if status != 200:
            return None, {key.lower(): value for key, value in response.headers.items()}
        assert response.headers["Cache-Control"] == "no-store"
        return (
            raw
            if response.headers.get_content_type().startswith("image/")
            else json.loads(raw)
        ), {key.lower(): value for key, value in response.headers.items()}


class Images:
    def __init__(self):
        buffer = BytesIO()
        Image.new("RGB", (64, 32), "navy").save(buffer, format="PNG")
        self.photo, self.calls = buffer.getvalue(), []

    def search(self, text, *, limit=5):
        self.calls.append("search")
        return [
            ImageSearchResult(
                1,
                "Synthetic",
                "https://upload.wikimedia.org/wikipedia/commons/test.png",
                "https://commons.wikimedia.org/wiki/File:test.png",
                "CC-BY",
                "Synthetic illustration credit",
                "image/png",
                len(self.photo),
                64,
                32,
                ("factory",),
            )
        ]

    def download(self, result):
        self.calls.append("download")
        return self.photo


class SyntheticPhotoClient:
    def __init__(self, sessions, cipher, now, account, photo_hash):
        self.sessions, self.now, self.account, self.photo_hash = (
            sessions,
            now,
            account,
            photo_hash,
        )
        self.events, self.uploaded, self.requests = [], [], []
        self.session = SimpleNamespace(save=lambda: "synthetic-illustration-session")
        self.channel = Channel(
            1234567891,
            "Synthetic output",
            ChatPhotoEmpty(),
            now,
            broadcast=True,
            admin_rights=ChatAdminRights(post_messages=True),
            access_hash=999,
        )

    async def connect(self):
        self.events.append("connect")

    async def disconnect(self):
        self.events.append("disconnect")

    async def is_user_authorized(self):
        return True

    async def get_me(self):
        return SimpleNamespace(id=1001)

    async def get_entity(self, peer):
        assert (peer.channel_id, peer.access_hash) == (1234567891, 999)
        self.events.append("permissions")
        return self.channel

    async def upload_file(self, content, *, file_name):
        assert digest(content) == self.photo_hash and file_name == "source.png"
        self.uploaded.append(digest(content))
        return InputFile(77, 1, "photo.png", "0" * 32)

    async def __call__(self, request):
        assert isinstance(request, SendMediaRequest)
        assert (
            request.message
            == DRAFT + "\n\nИллюстрация.\n\nSynthetic illustration credit"
        )
        assert request.allow_paid_stars == 0 and not request.allow_paid_floodskip
        with self.sessions() as session:
            job = session.scalar(
                select(models.PublicationJobModel).where(
                    models.PublicationJobModel.request_nonce == request.random_id
                )
            )
            assert job.state == "SENDING"
        self.requests.append(request.random_id)
        message = Message(
            501,
            PeerChannel(1234567891),
            self.now,
            request.message,
            out=True,
            post=True,
            media=MessageMediaPhoto(
                photo=Photo(123, 456, b"synthetic", self.now, [], 1)
            ),
        )
        return Updates(
            [
                UpdateMessageID(501, request.random_id),
                UpdateNewChannelMessage(message, 10, 1),
            ],
            [],
            [],
            self.now,
            1,
        )


def runner(sessions, root, cipher, now, client=None):
    publisher = (
        None
        if client is None
        else ConfiguredTelegramPhotoPublisher(
            sessions,
            root,
            cipher=cipher,
            api_id=123,
            api_hash="a" * 32,
            client_factory=lambda _: client,
        )
    )
    return DurablePublicationRunner(
        sessions, root, publisher=publisher, cipher=cipher, clock=lambda: now
    )


def seed(sessions, root, cipher, now):
    if (root / FILE).exists() or (root / "illustration-result.json").exists():
        raise ValueError("Original illustration manifest already exists; never reseed")
    with sessions() as session:
        for model in (
            models.TelegramAccount,
            models.PublicationCandidateModel,
            models.RewriteJobModel,
            models.IllustrationReviewRecordModel,
            models.PublicationJobModel,
        ):
            if session.scalar(select(func.count()).select_from(model)) != 0:
                raise ValueError(
                    "Synthetic database is not empty; preserve partial fixture"
                )
    manifest = {
        "version": 1,
        "owner": OWNER,
        "created_at": now.isoformat(),
        "cases": {},
        "rewrites": [],
    }
    with sessions() as session:
        account = models.TelegramAccount(
            name="Synthetic illustration restart",
            telegram_user_id=1001,
            encrypted_session=cipher.encrypt("synthetic-illustration-session"),
            health_status="CONNECTED",
        )
        session.add(account)
        session.commit()
        manifest["account"] = account.id
        config = TelegramConfigurationService(session)
        donor = config.create_donor(account.id, -1001234567890, "Synthetic source")
        output = config.create_output(account.id, -1001234567891, "Synthetic output")
        mapping = config.create_mapping(donor["id"], output["id"], 100, 50)
        session.get(
            models.ChannelMappingModel, mapping["id"]
        ).media_policy = "LICENSED_LIBRARY"
        peer = models.TelegramPeerModel(
            telegram_account_id=account.id,
            telegram_channel_id=-1001234567891,
            encrypted_peer=cipher.encrypt(
                json.dumps(
                    {
                        "version": 1,
                        "account_id": str(account.id),
                        "user_id": 1001,
                        "channel_id": -1001234567891,
                        "access_hash": 999,
                    }
                )
            ),
        )
        session.add(peer)
        session.commit()
        manifest["peer"], manifest["peer_hash"] = (
            [account.id, -1001234567891],
            row_hash(peer),
        )
        manifest["account_hash"] = digest(account.encrypted_session)
        account_id = account.id
        session.commit()
        for index, kind in enumerate(KINDS):
            result = DurableIngestionWorkflow(
                session, configured_mapping_id=mapping["id"]
            ).ingest(
                TelegramMessage(
                    str(account_id),
                    "-1001234567890",
                    20 + index,
                    f"Завод открыл {3 + index} линии.",
                    media_type="photo",
                    media_id=str(123 + index),
                    media_protected=False,
                    source_updated_at=now,
                ),
                observed_at=now,
                sentiment="neutral",
                framing="neutral",
            )
            assert result.status == "REWRITE_QUEUED"
            job = session.scalar(
                select(models.RewriteJobModel)
                .order_by(models.RewriteJobModel.id.desc())
                .limit(1)
            )
            job.state = "SUCCEEDED"
            session.commit()
            drafts = RewriteOutputService(session)
            draft = drafts.record_succeeded_output(
                job.id, f"Открыты {3 + index} линии на заводе."
            )
            drafts.approve(draft["id"], activate_candidate=True)
            candidate = session.scalar(
                select(models.PublicationCandidateModel).where(
                    models.PublicationCandidateModel.content_key == job.content_key
                )
            )
            decision = session.scalar(
                select(models.EditorialDecisionModel).where(
                    models.EditorialDecisionModel.content_key == job.content_key
                )
            )
            manifest["rewrites"].append(job.id)
            manifest["cases"][kind] = {
                "candidate": candidate.id,
                "decision": decision.id,
            }
            session.commit()
        # Rejected ingestion is exercised with production admission and no provider.
        rejected = DurableIngestionWorkflow(
            session, configured_mapping_id=mapping["id"]
        ).ingest(
            TelegramMessage(
                str(account_id),
                "-1001234567890",
                99,
                "Synthetic hostile source",
                source_updated_at=now,
            ),
            observed_at=now,
            sentiment="negative",
            framing="hostile",
            protected_entities=("Украина",),
        )
        assert rejected.status == "REJECTED_EDITORIAL"
        manifest["rejected_decision"] = session.scalar(
            select(models.EditorialDecisionModel)
            .order_by(models.EditorialDecisionModel.id.desc())
            .limit(1)
        ).id
    images = Images()
    media = DurableMediaRunner(sessions, root, provider=images, clock=lambda: now)
    execution = runner(sessions, root, cipher, now)
    for kind, case in manifest["cases"].items():
        media.enqueue_candidate(case["candidate"], now=now)
        assert media.run_next(now=now) == "SUCCEEDED"
        path = f"/api/illustration-review/candidates/{case['candidate']}"
        http(path + "/presentation", authorized=False, status=401)
        presentation, headers = http(path + "/presentation")
        assert (
            presentation["source_text"]
            == f"Завод открыл {3 + KINDS.index(kind)} линии."
            and presentation["draft_text"]
            == f"Открыты {3 + KINDS.index(kind)} линии на заводе."
        )
        http(path + "/photo", status=409)
        photo, _ = http(path + "/photo", headers={"If-Match": headers["etag"]})
        review, _ = http(
            path + "/reviews",
            payload={
                "displayed_binding": presentation["binding"],
                "operation_key": "synthetic-" + kind,
                "verdict": "APPROVED_ILLUSTRATION",
                "illustration_acknowledged": True,
                "review_note": "Synthetic illustration; no event-photo claim",
            },
        )
        assert (
            review["reviewer_id"] == 17
            and review["provenance"] == "AUTHENTICATED_HUMAN_V1"
        )
        case.update(
            review=review["id"],
            binding=review["binding"],
            asset=review["binding"]["media_asset_id"],
            photo_hash=digest(photo),
        )
        _current, headers = http(path + "/presentation")
        photo, photo_headers = http(
            path + "/photo", headers={"If-Match": headers["etag"]}
        )
        assert (
            digest(photo) == case["photo_hash"]
            and photo_headers["etag"] == headers["etag"]
        )
        case["etag"] = headers["etag"]
        with sessions.begin() as session:
            candidate = session.get(models.PublicationCandidateModel, case["candidate"])
            candidate.state, candidate.eligible_at = (
                "SCHEDULED",
                now - timedelta(minutes=1),
            )
            plan = models.PlannedPublicationModel(
                candidate_id=candidate.id,
                output_channel_id=candidate.output_channel_id,
                scheduled_for=now - timedelta(seconds=KINDS.index(kind)),
                state="PLANNED",
            )
            session.add(plan)
            session.flush()
            case["planned"] = plan.id
        case["job"] = execution.enqueue(case["planned"], now=datetime.now(UTC))
        with sessions() as session:
            row = session.get(models.IllustrationReviewRecordModel, case["review"])
            audit = session.scalar(
                select(models.OutboxEventModel).where(
                    models.OutboxEventModel.aggregate_key
                    == f"illustration-review:{row.id}",
                    models.OutboxEventModel.event_type == "IllustrationReviewRecorded",
                )
            )
            case.update(
                review_hash=row_hash(row),
                audit=audit.id,
                audit_hash=row_hash(audit),
                snapshot_hash=digest(
                    session.get(
                        models.PublicationRequestSnapshotModel, case["job"]
                    ).encrypted_envelope
                ),
                request_nonce=session.get(
                    models.PublicationJobModel, case["job"]
                ).request_nonce,
            )
    assert images.calls == ["search", "download"] * 4
    validate_manifest(manifest)
    write_new(root, FILE, manifest)


def invalidate(sessions, root, manifest, now):
    revoked = manifest["cases"]["revoked"]
    result, _ = http(
        f"/api/illustration-review/records/{revoked['review']}/revocations",
        payload={
            "operation_key": "synthetic-revoke",
            "review_note": "Synthetic withdrawal before restart",
        },
    )
    with sessions.begin() as session:
        stale = manifest["cases"]["stale"]
        session.get(
            models.RewriteOutputModel, stale["binding"]["rewrite_output_id"]
        ).rewritten_text = "Changed synthetic draft"
        sending = manifest["cases"]["sending"]
        job = session.get(models.PublicationJobModel, sending["job"])
        job.state, job.claim_token, job.lease_expires_at = (
            "SENDING",
            "synthetic-abandoned-claim",
            now - timedelta(minutes=1),
        )
        job.attempts = 1
    with sessions() as session:
        revocation = session.get(models.IllustrationReviewRecordModel, result["id"])
        audit = session.scalar(
            select(models.OutboxEventModel).where(
                models.OutboxEventModel.aggregate_key
                == f"illustration-review:{result['id']}",
                models.OutboxEventModel.event_type == "IllustrationReviewRevoked",
            )
        )
        write_new(
            root,
            "illustration-invalidated.json",
            {
                "version": 1,
                "revocation": result["id"],
                "revocation_hash": row_hash(revocation),
                "audit": audit.id,
                "audit_hash": row_hash(audit),
            },
        )


def verify(sessions, root, cipher, manifest, *, final):
    validate_manifest(manifest)
    invalidated = read_manifest(root / "illustration-invalidated.json")
    validate_aux(invalidated)
    with sessions() as session:
        account = session.get(models.TelegramAccount, manifest["account"])
        assert digest(account.encrypted_session) == manifest["account_hash"]
        assert (
            cipher.decrypt(account.encrypted_session)
            == "synthetic-illustration-session"
        )
        assert (
            row_hash(session.get(models.TelegramPeerModel, tuple(manifest["peer"])))
            == manifest["peer_hash"]
        )
        assert (
            row_hash(
                session.get(
                    models.IllustrationReviewRecordModel, invalidated["revocation"]
                )
            )
            == invalidated["revocation_hash"]
        )
        assert (
            row_hash(session.get(models.OutboxEventModel, invalidated["audit"]))
            == invalidated["audit_hash"]
        )
        rewrites = session.scalars(select(models.RewriteJobModel)).all()
        assert [r.id for r in rewrites] == manifest["rewrites"] and all(
            r.state == "SUCCEEDED" and r.attempts == 0 for r in rewrites
        )
        assert (
            session.scalar(select(func.count()).select_from(models.RewriteUsageModel))
            == 0
        )
        reject = session.get(
            models.EditorialDecisionModel, manifest["rejected_decision"]
        )
        assert reject.status == "REJECT" and reject.rewrite_allowed is False
        assert (
            session.scalar(select(func.count()).select_from(models.PublicationJobModel))
            == 4
        )
        for kind, case in manifest["cases"].items():
            assert (
                row_hash(
                    session.get(models.IllustrationReviewRecordModel, case["review"])
                )
                == case["review_hash"]
            )
            assert (
                row_hash(session.get(models.OutboxEventModel, case["audit"]))
                == case["audit_hash"]
            )
            snapshot = session.get(models.PublicationRequestSnapshotModel, case["job"])
            assert digest(snapshot.encrypted_envelope) == case["snapshot_hash"]
            payload = json.loads(cipher.decrypt(snapshot.encrypted_envelope))
            assert (
                payload["version"] == 2
                and payload["envelope"]["illustration_review_id"] == case["review"]
            )
            saved = PublicationRequestSnapshots(sessions, cipher=cipher).read(
                case["job"]
            )
            assert saved.envelope.illustration_review_id == case["review"]
            job = session.get(models.PublicationJobModel, case["job"])
            assert job.request_nonce == case["request_nonce"]
            expected = (
                {
                    "approved": "SUCCEEDED",
                    "revoked": "BLOCKED",
                    "stale": "BLOCKED",
                    "sending": "NEEDS_RECONCILIATION",
                }[kind]
                if final
                else "SENDING"
                if kind == "sending"
                else "QUEUED"
            )
            assert job.state == expected
            assert job.sent_message_id == (
                501 if final and kind == "approved" else None
            )
            asset = session.get(models.MediaAssetModel, case["asset"])
            content = (root / asset.storage_key).read_bytes()
            assert len(content) <= 262144 and digest(content) == case["photo_hash"]
            with Image.open(BytesIO(content)) as photo:
                assert photo.size == (64, 32) and photo.format == "PNG"
    for kind, case in manifest["cases"].items():
        path = f"/api/illustration-review/candidates/{case['candidate']}"
        latest, _ = http(path + "/latest-review")
        assert latest["latest_review"]["id"] == case["review"]
        assert latest["latest_review"]["revoked"] == (kind == "revoked")
        if kind == "stale" or final and kind == "approved":
            http(path + "/presentation", status=409)
            http(path + "/photo", headers={"If-Match": case["etag"]}, status=409)
        else:
            presentation, headers = http(path + "/presentation")
            assert presentation["binding"] == case["binding"]
            content, _ = http(path + "/photo", headers={"If-Match": headers["etag"]})
            assert digest(content) == case["photo_hash"]
            if kind == "revoked":
                http(path + "/photo", headers={"If-Match": case["etag"]}, status=409)
    if final:
        result = read_manifest(root / "illustration-result.json")
        validate_aux(result, result=True)
        assert result == result_manifest(sessions, manifest)
        with sessions() as session:
            rows = session.scalars(
                select(models.PublicationDeliveryObservationModel)
            ).all()
            assert (
                len(rows) == 1
                and rows[0].job_id == manifest["cases"]["approved"]["job"]
            )
            observed = json.loads(cipher.decrypt(rows[0].encrypted_receipt))
            assert (
                observed["provenance"] == "DIRECT_RESPONSE" and observed["attempt"] == 1
            )
            assert observed["receipt"] == {
                "account_id": manifest["account"],
                "telegram_channel_id": -1001234567891,
                "request_nonce": result["nonce"],
                "message_id": 501,
            }


def main(mode):
    if mode not in {"seed", "invalidate", "verify-pending", "execute", "verify-final"}:
        raise ValueError("Unknown illustration probe mode")
    if (
        os.environ.get("NEWSFLOW_ILLUSTRATION_FIXTURE") != "1"
        or os.environ.get("DATABASE_URL") != URL
        or any(os.environ.get(flag) != "0" for flag in FLAGS)
    ):
        raise ValueError(
            "Complete isolated PostgreSQL identity and disabled workers required"
        )
    if load_runtime_master_key() != MASTER:
        raise ValueError("Original public fixture master key required")
    root = Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
    engine = create_engine(URL)
    sessions, cipher = sessionmaker(engine), SessionCipher(MASTER)
    try:
        if mode == "seed":
            seed(sessions, root, cipher, datetime.now(UTC))
        else:
            manifest = read_manifest(root / FILE)
            validate_manifest(manifest)
            now = datetime.fromisoformat(manifest["created_at"]) + timedelta(minutes=2)
            if mode == "invalidate":
                invalidate(sessions, root, manifest, now)
            elif mode == "execute":
                verify(sessions, root, cipher, manifest, final=False)
                case = manifest["cases"]["approved"]
                client = SyntheticPhotoClient(
                    sessions, cipher, now, manifest["account"], case["photo_hash"]
                )
                execution = runner(sessions, root, cipher, now, client)
                assert [execution.run_next(now=now) for _ in range(4)] == [
                    "SUCCEEDED",
                    "BLOCKED",
                    "BLOCKED",
                    "IDLE",
                ]
                assert client.uploaded == [case["photo_hash"]] and client.requests == [
                    case["request_nonce"]
                ]
                assert execution.run_next(now=now) == "IDLE"
                write_new(
                    root,
                    "illustration-result.json",
                    result_manifest(sessions, manifest),
                )
                verify(sessions, root, cipher, manifest, final=True)
            else:
                verify(sessions, root, cipher, manifest, final=mode == "verify-final")
    finally:
        engine.dispose()
    print(f"Synthetic illustration {mode}: PASS; real Telegram/AI calls=0")


if __name__ == "__main__":
    main(sys.argv[1])
