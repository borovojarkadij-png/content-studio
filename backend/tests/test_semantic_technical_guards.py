"""Fresh technical exclusions fence semantic admission, execution and evidence."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from test_semantic_approval import SyntheticVerifier
from test_semantic_runner import NOW

from newsflow.persistence.models import (
    ChannelMappingModel,
    ContentRevisionModel,
    DonorChannel,
    PublicationCandidateModel,
    RewriteOutputModel,
    SemanticEvidenceModel,
    SemanticVerificationJobModel,
)
from newsflow.services.durable_semantic_runner import DurableSemanticRunner
from newsflow.services.telegram_configuration import TelegramConfigurationService


@pytest.mark.parametrize("kind", ["custom-domain", "media-policy", "video", "hidden-youtube"])
@pytest.mark.parametrize("timing", ["admission", "queued-reopen", "during-call"])
def test_fresh_technical_exclusion_guards_semantic_work(semantic_store, kind, timing):
    with semantic_store.begin() as session:
        donor = DonorChannel(
            telegram_account_id=1, telegram_channel_id=-1001111111111, title="Synthetic"
        )
        session.add(donor)
        session.flush()
        for channel_id in (1, 2):
            mapping = ChannelMappingModel(
                donor_channel_id=donor.id,
                output_channel_id=channel_id,
                intake_percent=100,
                target_mix_percent=100,
            )
            session.add(mapping)
            session.flush()
            session.get(PublicationCandidateModel, channel_id).mapping_id = mapping.id
        session.scalar(select(ContentRevisionModel)).link_destinations = [
            "https://example.org/news"
        ]

    def exclude():
        with semantic_store() as session:
            if kind in {"video", "hidden-youtube"}:
                revision = session.scalar(select(ContentRevisionModel))
                if kind == "video":
                    revision.media_type = "video"
                else:
                    revision.link_destinations = ["https://youtube.com/watch?v=synthetic"]
                session.commit()
            else:
                for mapping_id in (1, 2):
                    TelegramConfigurationService(session).configure_mapping_filters(
                        mapping_id,
                        allowed_media_types=[] if kind == "media-policy" else ["text", "photo"],
                        blocked_domains=["example.org"] if kind == "custom-domain" else [],
                        ad_markers=[],
                    )

    provider = SyntheticVerifier(change=exclude if timing == "during-call" else None)
    factories = []

    def make_provider(release):
        factories.append(release)
        return provider

    execution = DurableSemanticRunner(
        semantic_store, verifier_for_release=make_provider, clock=lambda: NOW
    )
    if timing == "admission":
        exclude()
        assert execution.enqueue_pending(now=NOW) == 0
        assert execution.run_next(now=NOW) == "IDLE"
    else:
        assert execution.enqueue_pending(now=NOW) == 2
        if timing == "queued-reopen":
            exclude()
        reopened_engine = create_engine(semantic_store.kw["bind"].url)
        try:
            reopened = DurableSemanticRunner(
                sessionmaker(reopened_engine), verifier_for_release=make_provider, clock=lambda: NOW
            )
            assert reopened.run_next(now=NOW) == "BLOCKED"
        finally:
            reopened_engine.dispose()
    assert len(factories) == (1 if timing == "during-call" else 0)
    assert len(provider.calls) == (1 if timing == "during-call" else 0)
    with semantic_store() as session:
        assert session.scalar(select(SemanticEvidenceModel)) is None
        assert list(session.scalars(select(RewriteOutputModel.approval_state))) == [
            "PENDING",
            "PENDING",
        ]
        jobs = session.scalars(
            select(SemanticVerificationJobModel).order_by(SemanticVerificationJobModel.id)
        ).all()
        assert [(job.state, job.attempts) for job in jobs] == (
            [] if timing == "admission" else [("BLOCKED", 1), ("QUEUED", 0)]
        )
