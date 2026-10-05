from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TEST_KEY = "test-only-key-" + "a" * 32
PAYLOAD = {"customer_reference": "customer-demo-001", "amount_minor": 1500, "currency": "USD"}


@pytest.fixture
def client():
    with TestClient(create_app(api_key=TEST_KEY)) as instance:
        yield instance


def headers(key="order-test-001"):
    return {"X-API-Key": TEST_KEY, "Idempotency-Key": key}


def test_health_endpoints(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


@pytest.mark.parametrize("key", [None, "wrong-key"])
def test_rejects_invalid_auth(client, key):
    h = {"Idempotency-Key": "auth-test"}
    if key is not None:
        h["X-API-Key"] = key
    assert client.post("/api/v1/orders", json=PAYLOAD, headers=h).status_code == 401


def test_create_and_get(client):
    response = client.post("/api/v1/orders", json=PAYLOAD, headers=headers())
    assert response.status_code == 201
    assert response.json()["status"] == "PENDING"
    assert response.json()["amount_minor"] == 1500
    assert response.headers["Idempotency-Replayed"] == "false"
    fetched = client.get(response.headers["Location"], headers={"X-API-Key": TEST_KEY})
    assert fetched.status_code == 200
    assert fetched.json() == response.json()


def test_replay(client):
    first = client.post("/api/v1/orders", json=PAYLOAD, headers=headers())
    replay = client.post("/api/v1/orders", json=PAYLOAD, headers=headers())
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.headers["Idempotency-Replayed"] == "true"


def test_conflict(client):
    client.post("/api/v1/orders", json=PAYLOAD, headers=headers())
    changed = {**PAYLOAD, "amount_minor": 2000}
    assert client.post("/api/v1/orders", json=changed, headers=headers()).status_code == 409


@pytest.mark.parametrize("changes", [
    {"amount_minor": 0}, {"amount_minor": -1}, {"amount_minor": 15.5},
    {"amount_minor": "1500"}, {"currency": "EUR"},
    {"customer_reference": "   "}, {"unexpected_field": "value"},
])
def test_invalid_payload(client, changes):
    assert client.post("/api/v1/orders", json={**PAYLOAD, **changes}, headers=headers()).status_code == 422


def test_missing_idempotency_key(client):
    assert client.post("/api/v1/orders", json=PAYLOAD, headers={"X-API-Key": TEST_KEY}).status_code == 422


def test_unknown_order(client):
    assert client.get(f"/api/v1/orders/{uuid4()}", headers={"X-API-Key": TEST_KEY}).status_code == 404


def test_read_requires_auth(client):
    assert client.get(f"/api/v1/orders/{uuid4()}").status_code == 401


def test_invalid_configuration():
    with pytest.raises(RuntimeError):
        create_app(api_key="too-short")
