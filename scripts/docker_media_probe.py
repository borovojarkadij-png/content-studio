"""Synthetic media claim/recovery/storage probe. Never runs against operational DBs."""

import io
import json
import os
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from newsflow.persistence.models import (
    MediaAcquisitionJobModel,
    MediaAssetModel,
    PublicationCandidateModel,
)
from newsflow.providers.commons_images import ImageSearchResult
from newsflow.services.durable_media_runner import DurableMediaRunner, MediaClaim
from newsflow.services.media_selection import MediaSelectionBlocked

KEY = "synthetic-semantic:@synthetic_semantic:910:revision:1"


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "navy").save(buffer, format="PNG")
    return buffer.getvalue()


class SyntheticImages:
    calls = 0

    def search(self, query, *, limit=5):
        self.calls += 1
        return [
            ImageSearchResult(
                1,
                "Synthetic only",
                "https://upload.wikimedia.org/wikipedia/commons/a/ab/Synthetic.png",
                "https://commons.wikimedia.org/wiki/File:Synthetic.png",
                "CC0",
                "Synthetic test fixture, not a real Commons asset",
                "image/png",
                len(photo()),
                4,
                4,
                ("synthetic", "factory"),
            )
        ]

    def download(self, result):
        self.calls += 1
        return photo()


def main(mode):
    url = os.environ["DATABASE_URL"]
    if (
        os.getenv("NEWSFLOW_VERIFICATION_PROBE") != "1"
        or make_url(url).database != "newsflow_verification"
    ):
        raise RuntimeError("Media probe requires isolated verification DB")
    engine = create_engine(url)
    factory = sessionmaker(engine)
    root = Path(os.environ["NEWSFLOW_MEDIA_ROOT"])
    images = SyntheticImages()
    runner = DurableMediaRunner(factory, root, provider=images)
    with factory() as session:
        candidate = session.scalars(
            select(PublicationCandidateModel).where(PublicationCandidateModel.content_key == KEY)
        ).one()
        candidate_id = candidate.id
        if mode == "seed":
            assert session.scalar(select(MediaAcquisitionJobModel.id)) is None
            candidate.media_policy = "LICENSED_LIBRARY"
            session.commit()
    if mode == "seed":
        assert runner.enqueue_pending(now=datetime.now(UTC)) == 1
        assert runner.claim_next(now=datetime.now(UTC)).attempt == 1
        assert images.calls == 0
    elif mode == "recover":
        with factory() as session:
            job = session.scalars(select(MediaAcquisitionJobModel)).one()
            old = MediaClaim(job.id, job.claim_token, job.attempts)
        recovered = runner.claim_next(now=datetime.now(UTC))
        assert recovered is not None and recovered.attempt == 2
        assert runner.execute(old) == "LOST_LEASE"
        assert runner.execute(recovered) == "SUCCEEDED"
        assert images.calls == 2
    elif mode == "verify":
        with factory() as session:
            job = session.scalars(select(MediaAcquisitionJobModel)).one()
            asset = session.get(MediaAssetModel, job.selected_asset_id)
            assert job.state == "SUCCEEDED" and job.attempts == 2 and job.claim_token is None
            assert asset.license_code == "CC0" and asset.origin == "LICENSED_LIBRARY"
            assert (root / asset.storage_key).read_bytes() == photo()
            assert sha256(photo()).hexdigest() == asset.sha256
        assert runner.enqueue_pending(now=datetime.now(UTC)) == 0
        with urlopen(
            f"http://api:8000/api/telegram/publication-candidates/{candidate_id}/media-acquisition",
            timeout=5,
        ) as response:
            status = json.load(response)
        assert status["state"] == "SUCCEEDED" and status["selected_allowed"] is True
    elif mode == "blocked":
        try:
            runner._acquisition.acquire(candidate_id)
        except MediaSelectionBlocked:
            pass
        else:
            raise AssertionError("Revoked approval did not block media acquisition")
        assert images.calls == 0
        with urlopen(
            f"http://api:8000/api/telegram/publication-candidates/{candidate_id}/media-acquisition",
            timeout=5,
        ) as response:
            status = json.load(response)
        assert status["state"] == "SUCCEEDED" and status["selected_allowed"] is False
    else:
        raise ValueError("Unknown media mode")
    engine.dispose()
    print(f"Synthetic media {mode} PASS; network calls=0; publications=0")


if __name__ == "__main__":
    main(sys.argv[1])
