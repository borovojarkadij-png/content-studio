import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from newsflow.persistence.models import Base, RewriteProviderSettingModel
from newsflow.security.session_cipher import SessionCipher
from newsflow.services.rewrite_provider_settings import RewriteProviderSettingsService


class RecordingModelCatalog:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def list_models(self, *, provider: str, api_key: str) -> tuple[str, ...]:
        self.calls.append((provider, api_key))
        return (
            ("gpt-test-a", "gpt-test-b")
            if provider == "OPENAI"
            else ("alpha/rewrite:free", "openrouter/free")
        )


@pytest.mark.parametrize(
    "models",
    [
        ("alpha/rewrite:free",) * 2,
        tuple(f"alpha/{n}:free" for n in range(9)),
        ("alpha/rewrite:free,paid/model",),
        ("alpha/rewrite:free\n",),
    ],
)
def test_free_settings_reject_unsafe_or_unbounded_model_lists_before_persisting(models):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        )
        with pytest.raises(ValueError):
            service.configure_openrouter(api_key="synthetic", fallback_models=models)
        assert session.scalars(select(RewriteProviderSettingModel)).all() == []
    engine.dispose()


def test_openrouter_settings_encrypt_key_and_expose_only_free_model_configuration() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )

        configured = service.configure_openrouter(
            api_key="synthetic-openrouter-key",
            fallback_models=("alpha/rewrite:free", "beta/rewrite:free"),
        )

        assert configured == {
            "provider": "OPENROUTER",
            "configured": True,
            "primary_model": "alpha/rewrite:free",
            "fallback_models": ("alpha/rewrite:free", "beta/rewrite:free"),
        }
        stored = session.scalar(select(RewriteProviderSettingModel))
        assert stored is not None
        assert stored.encrypted_api_key != "synthetic-openrouter-key"
        assert "synthetic-openrouter-key" not in str(service.list_settings())


def test_openrouter_settings_reject_paid_fallback_without_persisting_secret() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )

        try:
            service.configure_openrouter(
                api_key="synthetic-openrouter-key",
                fallback_models=("openai/gpt-5",),
            )
        except ValueError as exc:
            assert "free" in str(exc).lower()
        else:
            raise AssertionError("Paid OpenRouter fallback must be rejected")

        assert session.scalars(select(RewriteProviderSettingModel)).all() == []


def test_replacing_or_removing_provider_key_never_returns_plaintext() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )
        service.configure_openrouter(
            api_key="first-synthetic-key", fallback_models=("alpha/rewrite:free",)
        )
        replacement = service.configure_openrouter(
            api_key="second-synthetic-key", fallback_models=("beta/rewrite:free",)
        )

        assert replacement["primary_model"] == "beta/rewrite:free"
        assert "synthetic-key" not in str(replacement)
        assert service.remove_provider("OPENROUTER") == {
            "provider": "OPENROUTER",
            "configured": False,
        }
        assert service.list_settings() == []


def test_openai_settings_store_selected_rewrite_model_without_returning_key() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )

        configured = service.configure_openai(
            api_key="synthetic-openai-key", model="gpt-test-rewrite"
        )

        assert configured == {
            "provider": "OPENAI",
            "configured": True,
            "primary_model": "gpt-test-rewrite",
            "fallback_models": (),
        }
        assert "synthetic-openai-key" not in str(service.list_settings())


def test_model_catalog_uses_decrypted_key_only_server_side() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )
        service.configure_openai(api_key="synthetic-openai-key", model="gpt-test-a")
        catalog = RecordingModelCatalog()

        models = service.available_models("OPENAI", catalog=catalog)

        assert models == ("gpt-test-a", "gpt-test-b")
        assert catalog.calls == [("OPENAI", "synthetic-openai-key")]


def test_openrouter_catalog_never_exposes_a_paid_model() -> None:
    class MixedCatalog:
        def list_models(self, *, provider: str, api_key: str) -> tuple[str, ...]:
            assert provider == "OPENROUTER"
            assert api_key == "synthetic-openrouter-key"
            return ("vendor/free:free", "openai/gpt-paid", "openrouter/free")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = RewriteProviderSettingsService(
            session, cipher=SessionCipher(Fernet.generate_key().decode("ascii"))
        )
        service.configure_openrouter(
            api_key="synthetic-openrouter-key",
            fallback_models=("vendor/free:free",),
        )

        assert service.available_models("OPENROUTER", catalog=MixedCatalog()) == (
            "vendor/free:free",
            "openrouter/free",
        )
