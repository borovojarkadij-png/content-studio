import pytest
from sqlalchemy import create_engine, text

from alembic import command
from newsflow.migrate import runtime_migration_config


def test_semantic_migration_preserves_existing_drafts_and_guards_evidence_loss(
    tmp_path, monkeypatch
):
    url = f"sqlite:///{tmp_path / 'isolated-semantic.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = runtime_migration_config()
    command.upgrade(config, "a91c73bd204e")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO telegram_accounts(id,name,telegram_user_id,encrypted_session,health_status) VALUES(1,'synthetic',1001,'','DISCONNECTED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO output_channels(id,telegram_account_id,telegram_channel_id,title) VALUES(1,1,-1000000000001,'synthetic')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rewrite_jobs(id,content_key,output_channel_id,idempotency_key,state) VALUES(1,'synthetic',1,'synthetic','SUCCEEDED')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rewrite_outputs(id,rewrite_job_id,output_channel_id,content_key,rewritten_text,approval_state) VALUES(1,1,1,'synthetic','existing draft','APPROVED')"
            )
        )
    command.upgrade(config, "head")
    command.check(config)
    with engine.begin() as connection:
        assert connection.execute(
            text("SELECT rewritten_text,approval_state,approval_method FROM rewrite_outputs")
        ).one() == ("existing draft", "APPROVED", "MANUAL")
        connection.execute(
            text(
                "INSERT INTO semantic_verifier_releases(provider,model,prompt_version,benchmark_version,report_sha256,active) VALUES('OPENAI','synthetic','semantic-facts-v1','semantic-facts-v1',:digest,false)"
            ),
            {"digest": "a" * 64},
        )
    with pytest.raises(RuntimeError, match="Refusing"):
        command.downgrade(config, "a91c73bd204e")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM semantic_verifier_releases")) == 1
        assert (
            connection.scalar(text("SELECT rewritten_text FROM rewrite_outputs"))
            == "existing draft"
        )
    engine.dispose()
