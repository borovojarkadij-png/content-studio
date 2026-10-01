from fastapi.testclient import TestClient

from newsflow.app import app


def test_bulk_donor_import_returns_accepted_and_rejected_identifiers() -> None:
    response = TestClient(app).post(
        "/api/telegram/donors:bulk-import",
        json={"raw_text": "@valid_source\ninvalid source"},
    )

    assert response.status_code == 200
    assert response.json() == {"accepted": ["@valid_source"], "rejected": ["invalid source"]}


def test_incoming_posts_endpoint_exposes_an_empty_moderation_inbox() -> None:
    response = TestClient(app).get("/api/telegram/incoming-posts")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_telegram_accounts_endpoint_exposes_empty_configuration_list() -> None:
    response = TestClient(app).get("/api/telegram/accounts")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_create_telegram_account_validates_configuration_identity() -> None:
    response = TestClient(app).post(
        "/api/telegram/accounts",
        json={"name": "Основной", "telegram_user_id": 1001, "encrypted_session": "ciphertext"},
    )

    assert response.status_code == 201
    assert response.json()["telegram_user_id"] == 1001
