from datetime import UTC, datetime

import pytest


def test_disabled_worker_has_no_database_secret_or_provider_activity():
    from newsflow.worker import run_rewrite_tick

    def forbidden():
        raise AssertionError("Disabled network worker touched database")

    assert (
        run_rewrite_tick(forbidden, enabled=False, cipher=None, now=datetime.now(UTC)) == "DISABLED"
    )


@pytest.mark.parametrize("value", ["yes", "true", "", "2"])
def test_network_enable_policy_rejects_ambiguous_values(value):
    from newsflow.worker import rewrite_enabled

    with pytest.raises(ValueError):
        rewrite_enabled(value)


def test_enabled_worker_requires_stable_cipher_before_claim():
    from newsflow.worker import run_rewrite_tick

    with pytest.raises(ValueError, match="cipher"):
        run_rewrite_tick(lambda: None, enabled=True, cipher=None, now=datetime.now(UTC))


def test_explicit_free_worker_executes_saved_free_model_without_openai_credentials(tmp_path):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from test_openrouter_structured import FreeHttp, reply

    from newsflow.domain.durable_ingestion import DurableIngestionWorkflow
    from newsflow.domain.technical_filters import MappingTechnicalFilter
    from newsflow.persistence.models import Base, RewriteOutputModel, RewriteUsageModel
    from newsflow.providers.telegram import TelegramMessage
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.services.rewrite_provider_settings import RewriteProviderSettingsService
    from newsflow.services.telegram_configuration import TelegramConfigurationService
    from newsflow.worker import run_rewrite_tick

    engine = create_engine(f"sqlite:///{tmp_path / 'free-worker.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    cipher = SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
    with factory() as session:
        config = TelegramConfigurationService(session)
        account = config.create_account("Synthetic", 1001)
        donor = config.create_donor(account["id"], -1001234567890, "Donor")
        output = config.create_output(account["id"], -1001234567891, "Output")
        mapping = config.create_mapping(donor["id"], output["id"], 100, 0)
        DurableIngestionWorkflow(
            session,
            technical_filter=MappingTechnicalFilter(
                mapping_id=str(mapping["id"]), output_channel_id=output["id"]
            ),
        ).ingest(
            TelegramMessage("synthetic", "@donor", 1, "Открыто 10 объектов"),
            observed_at=datetime.now(UTC),
        )
        RewriteProviderSettingsService(session, cipher=cipher).configure_openrouter(
            api_key="synthetic", fallback_models=("a/model:free",)
        )
    assert (
        run_rewrite_tick(
            factory,
            enabled=True,
            cipher=cipher,
            now=datetime.now(UTC),
            opener=FreeHttp([reply()]),
            provider="OPENROUTER",
        )
        == "SUCCEEDED"
    )
    with factory() as session:
        assert session.scalar(select(RewriteUsageModel)).provider == "OPENROUTER"
        assert session.scalar(select(RewriteOutputModel)).approval_state == "PENDING"
    engine.dispose()


def test_invalid_provider_does_not_claim_jobs_or_silently_select_openai():
    from newsflow.security.session_cipher import SessionCipher
    from newsflow.worker import run_rewrite_tick

    def forbidden():
        raise AssertionError("Invalid provider claimed a job")

    with pytest.raises(ValueError):
        run_rewrite_tick(
            forbidden,
            enabled=True,
            cipher=SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="),
            now=datetime.now(UTC),
            provider="typo",
        )
