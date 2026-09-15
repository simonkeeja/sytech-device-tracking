from uuid import uuid4
from fastapi.testclient import TestClient
from backend.app import app
from backend.database import db
from backend import security
import pytest

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

@pytest.fixture
def owner():
    return {"Authorization": "Bearer " + security.create_session(1)}

@pytest.fixture
def admin():
    uid = db.create_user("Admin", "admin-test", "alt", security.hash_password("long-test-password"), role="admin")
    return {"Authorization": "Bearer " + security.create_session(uid)}

def test_health(client):
    assert client.get("/api/health").status_code == 200

@pytest.mark.parametrize("route", ["/api/devices", "/api/devices/1", "/api/devices/1/preview", "/api/devices/1/affidavit-pdf"])
def test_auth_required(client, route):
    assert client.get(route).status_code == 401

def test_registration_login(client):
    body = dict(full_name_omang="Test Owner", primary_contact="test-contact", alt_contact="alt", password="long-test-password")
    uid = client.post("/api/users/register", json=body).json()["user_id"]
    login = client.post("/api/auth/login", json={"primary_contact": body["primary_contact"], "password": body["password"]})
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    payload = dict(user_id=uid, device_type="smartphone", brand="Test", model="Test", hardware_identifier="test-hardware", purchase_price_bwp=6000, master_backup_pin="123456")
    response = client.post("/api/devices/register", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["device"]["success_fee_calculated"] == 1500
    assert "master_backup_pin" not in response.json()["device"]
    assert security.verify_password("123456", db.get_device(response.json()["device_id"])["master_backup_pin"])
    assert response.json()["ocr_verification"]["is_valid"] is False
    assert client.get("/api/devices/1", headers=headers).status_code == 403
    payload["purchase_price_bwp"] = -1
    assert client.post("/api/devices/register", json=payload, headers=headers).status_code == 422

def test_secrets_and_unpaid_intel_hidden(client, owner):
    detail = client.get("/api/devices/1", headers=owner).json()
    assert "password_hash" not in detail["user"]
    assert "master_backup_pin" not in detail["device"]
    assert detail["intel_logs"] == []
    assert all("master_backup_pin" not in d for d in client.get("/api/devices", headers=owner).json())
    assert not client.get("/api/devices/1/preview", headers=owner).json()["photo_url"]
    assert client.get("/api/devices/1/affidavit-pdf", headers=owner).status_code == 403

@pytest.mark.parametrize("service", ["registration_only", "data_recovery_only"])
def test_wrong_service_does_not_unlock(client, owner, service):
    assert client.post("/api/invoices/checkout", headers=owner, json=dict(idempotency_key=uuid4().hex, device_id=1, selected_service=service, payment_method="Orange Money")).status_code == 200
    assert not client.get("/api/devices/1/preview", headers=owner).json()["is_settled"]
    assert client.get("/api/devices/1/affidavit-pdf", headers=owner).status_code == 403

def test_dossier_entitlement_survives_later_invoice(client, owner):
    for service in ["full_intel_dossier", "registration_only"]:
        assert client.post("/api/invoices/checkout", headers=owner, json=dict(idempotency_key=uuid4().hex, device_id=1, selected_service=service, payment_method="Orange Money")).status_code == 200
    assert client.get("/api/devices/1/preview", headers=owner).json()["is_settled"]
    assert client.get("/api/devices/1/affidavit-pdf", headers=owner).headers["content-type"] == "application/pdf"

def test_demo_disabled(client, owner, admin, monkeypatch):
    monkeypatch.delenv("SYTECH_DEMO_MODE")
    assert client.post("/api/invoices/checkout", headers=owner, json=dict(idempotency_key=uuid4().hex, device_id=1, selected_service="full_intel_dossier", payment_method="Cash")).status_code == 503
    assert client.post("/api/telemetry/ingress", headers=admin, json=dict(device_id=1, trigger_type="sim_swap")).status_code == 503

def test_telemetry_restricted(client, owner):
    payload = dict(device_id=1, trigger_type="sim_swap")
    assert client.post("/api/telemetry/ingress", json=payload).status_code == 401
    assert client.post("/api/telemetry/ingress", json=payload, headers=owner).status_code == 403

def test_reset_permissions_and_single_use(client, owner, admin):
    assert client.post("/api/devices/1/generate-remote-token", headers=owner).status_code == 403
    token = client.post("/api/devices/1/generate-remote-token", headers=admin).json()["remote_token"]
    payload = dict(device_id=1, reset_token=token)
    assert client.post("/api/devices/1/apply-remote-token", headers=owner, json=payload).status_code == 200
    assert client.post("/api/devices/1/apply-remote-token", headers=owner, json=payload).status_code == 403

def test_session_expiry(client, monkeypatch):
    token = security.create_session(1)
    monkeypatch.setattr(security.time, "time", lambda: 10**12)
    assert client.get("/api/devices", headers={"Authorization": "Bearer " + token}).status_code == 401

def test_websocket_roles(client, owner, admin):
    from starlette.websockets import WebSocketDisconnect
    for token in ["invalid", owner["Authorization"].split()[1]]:
        with client.websocket_connect("/ws/feed") as ws:
            ws.send_text(token)
            with pytest.raises(WebSocketDisconnect):
                ws.receive_text()
    with client.websocket_connect("/ws/feed") as ws:
        ws.send_text(admin["Authorization"].split()[1])
        assert ws.receive_json()["event"] == "AUTHENTICATED"
        response = client.post("/api/telemetry/ingress", headers=admin, json=dict(device_id=1, trigger_type="sim_swap"))
        assert response.status_code == 200
        assert ws.receive_json()["event"] == "TELEMETRY_INGRESS"


def test_reset_expiration(client, owner, admin, monkeypatch):
    from backend.app import ACTIVE_RESET_TOKENS
    token = client.post("/api/devices/1/generate-remote-token", headers=admin).json()["remote_token"]
    ACTIVE_RESET_TOKENS[1] = (token, 0)
    assert client.post("/api/devices/1/apply-remote-token", headers=owner, json=dict(device_id=1, reset_token=token)).status_code == 403


def test_legacy_pin(client, owner):
    for pin, code in [("0000", 409), ("7924", 409)]:
        assert client.post("/api/devices/1/verify-master-pin", headers=owner, json=dict(device_id=1, entered_pin=pin)).status_code == code
