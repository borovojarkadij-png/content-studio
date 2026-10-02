import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from newsflow.app import app
from newsflow.persistence.models import Base


@pytest.fixture
def client(monkeypatch, tmp_path):
    database_url = f"sqlite:///{tmp_path / 'api.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_incoming_posts_endpoint_exposes_an_empty_moderation_inbox() -> None:
    response = TestClient(app).get("/api/telegram/incoming-posts")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_telegram_accounts_endpoint_exposes_empty_configuration_list(client) -> None:
    response = client.get("/api/telegram/accounts")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_create_telegram_account_validates_configuration_identity(client) -> None:
    response = client.post(
        "/api/telegram/accounts",
        json={"name": "Основной", "telegram_user_id": 6000000001},
    )

    assert response.status_code == 201
    assert response.json()["telegram_user_id"] == 6000000001
    assert response.json()["health_status"] == "DISCONNECTED"
    assert client.get("/api/telegram/accounts").json()["items"] == [response.json()]


def test_configured_channels_and_mapping_survive_an_independent_client(client):
    account = client.post(
        "/api/telegram/accounts",
        json={
            "name": "Primary",
            "telegram_user_id": 1001,
        },
    ).json()
    donor = client.post(
        "/api/telegram/donors",
        json={
            "telegram_account_id": account["id"],
            "telegram_channel_id": -1001234567890,
            "title": "Source",
        },
    ).json()
    output = client.post(
        "/api/telegram/output-channels",
        json={
            "telegram_account_id": account["id"],
            "telegram_channel_id": -1009876543210,
            "title": "Destination",
        },
    ).json()
    payload = {
        "donor_channel_id": donor["id"],
        "output_channel_id": output["id"],
        "intake_percent": 20,
        "target_mix_percent": 80,
    }
    mapping = client.post("/api/telegram/mappings", json=payload)
    assert mapping.status_code == 201
    assert client.post("/api/telegram/mappings", json=payload).json() == mapping.json()
    with TestClient(app) as new_client:
        assert new_client.get("/api/telegram/donors").json()["items"] == [donor]
        assert new_client.get("/api/telegram/output-channels").json()["items"] == [output]
        updated = new_client.patch(
            f"/api/telegram/mappings/{mapping.json()['id']}",
            json={
                "intake_percent": 35,
                "target_mix_percent": 65,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["intake_percent"] == 35


def test_bulk_donor_import_persists_pending_identifiers_without_fake_channels(client):
    account = client.post(
        "/api/telegram/accounts",
        json={
            "name": "Primary",
            "telegram_user_id": 1001,
        },
    ).json()
    payload = {
        "telegram_account_id": account["id"],
        "raw_text": "@Valid_source\n@valid_SOURCE\ninvalid source",
    }
    result = client.post("/api/telegram/donors:bulk-import", json=payload)
    assert result.status_code == 200
    assert result.json() == {
        "accepted": ["@valid_source"],
        "duplicates": ["@valid_source"],
        "rejected": ["invalid source"],
        "status": "PENDING_RESOLUTION",
    }
    assert client.get("/api/telegram/donors").json() == {"items": []}
    assert (
        client.get("/api/telegram/donor-imports").json()["items"][0]["status"]
        == "PENDING_RESOLUTION"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("telegram_user_id", 2222),
        ("health_status", "CONNECTED"),
        ("encrypted_session", "plaintext"),
        ("rewrite_allowed", True),
    ],
)
def test_account_patch_forbids_identity_secrets_health_and_editorial_bypass(client, field, value):
    account = client.post(
        "/api/telegram/accounts",
        json={
            "name": "Primary",
            "telegram_user_id": 1001,
        },
    ).json()
    result = client.patch(
        f"/api/telegram/accounts/{account['id']}", json={"name": "Rename", field: value}
    )
    assert result.status_code == 422
    assert client.get("/api/telegram/accounts").json()["items"] == [account]


@pytest.mark.parametrize(
    "path", ["accounts", "donors", "output-channels", "mappings", "donor-imports"]
)
def test_missing_database_fails_visibly_instead_of_in_memory_success(monkeypatch, path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert TestClient(app).get(f"/api/telegram/{path}").status_code == 503


def test_identity_conflict_and_missing_reference_are_safe_http_errors(client):
    assert (
        client.post(
            "/api/telegram/accounts", json={"name": "Primary", "telegram_user_id": 1001}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/telegram/accounts", json={"name": "Other", "telegram_user_id": 1001}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/telegram/donors",
            json={
                "telegram_account_id": 999,
                "telegram_channel_id": -1001234567890,
                "title": "Source",
            },
        ).status_code
        == 404
    )
