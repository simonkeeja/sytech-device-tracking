from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import sqlite3
import pytest
from backend import security
from backend.database import db, schema
from tests.test_schema_and_api import client, owner, admin


def test_contact_normalization_and_unique_constraint(client):
    body = dict(full_name_omang="Owner", primary_contact="+267 (71) 555-555", alt_contact="alt", password="long-test-password")
    assert client.post("/api/users/register", json=body).status_code == 200
    body["primary_contact"] = "0026771555555"
    assert client.post("/api/users/register", json=body).status_code == 409
    assert client.post("/api/auth/login", json=dict(primary_contact=body["primary_contact"], password=body["password"])).status_code == 200
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("Duplicate", "+26771555555", "alt", "disabled")


def test_foreign_keys_and_migration_preflight():
    conn = schema.get_db_connection()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO receipts(device_id, receipt_image_url) VALUES (9999, 'test')")
        conn.rollback()
        conn.execute("DROP INDEX users_contact_unique")
        conn.execute("INSERT INTO users(full_name_omang,primary_contact,alt_contact,password_hash) VALUES ('Duplicate', '+26772111222', '', 'disabled')")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="duplicate account contacts"):
        schema.init_db()
    conn = schema.get_db_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    finally:
        conn.close()


def test_login_throttle_and_expiry(client, monkeypatch):
    tick = [100.0]
    monkeypatch.setattr(security.time, "monotonic", lambda: tick[0])
    for _ in range(10):
        assert client.post("/api/auth/login", json=dict(primary_contact="missing", password="wrong")).status_code == 401
    response = client.post("/api/auth/login", json=dict(primary_contact=" MISSING ", password="wrong"))
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    tick[0] += 901
    assert client.post("/api/auth/login", json=dict(primary_contact="missing", password="wrong")).status_code == 401


def test_owner_replaces_legacy_pin_and_reset_throttle(client, owner, admin):
    conn = db.get_db_connection()
    try:
        conn.execute("UPDATE users SET password_hash=? WHERE user_id=1", (security.hash_password("owner-password-long"),))
        conn.commit()
    finally:
        conn.close()
    body = dict(password="owner-password-long", new_pin="654321")
    assert client.put("/api/devices/1/backup-pin", headers=admin, json=body).status_code == 403
    assert client.put("/api/devices/1/backup-pin", headers=owner, json={**body, "password": "wrong"}).status_code == 403
    assert client.put("/api/devices/1/backup-pin", headers=owner, json=body).status_code == 200
    assert security.verify_password("654321", db.get_device(1)["master_backup_pin"])
    assert client.post("/api/devices/1/verify-master-pin", headers=owner, json=dict(device_id=1, entered_pin="654321")).status_code == 200
    for _ in range(4):
        assert client.post("/api/devices/1/verify-master-pin", headers=owner, json=dict(device_id=1, entered_pin="000000")).status_code == 403
    assert client.post("/api/devices/1/verify-master-pin", headers=owner, json=dict(device_id=1, entered_pin="654321")).status_code == 429
    for _ in range(5):
        assert client.post("/api/devices/1/apply-remote-token", headers=owner, json=dict(device_id=1, reset_token="wrong")).status_code == 403
    assert client.post("/api/devices/1/apply-remote-token", headers=owner, json=dict(device_id=1, reset_token="wrong")).status_code == 429


def test_checkout_retry_conflict_and_report_failure(client, owner, monkeypatch):
    from backend.services import affidavit_generator
    def broken_report(*args, **kwargs):
        raise OSError("Report temporarily unavailable")
    monkeypatch.setattr(affidavit_generator, "generate_police_affidavit_pdf", broken_report)
    body = dict(idempotency_key=uuid4().hex, device_id=1, selected_service="full_intel_dossier", payment_method="Cash")
    first = client.post("/api/invoices/checkout", headers=owner, json=body)
    assert first.status_code == 200
    retry = client.post("/api/invoices/checkout", headers=owner, json=body)
    assert retry.json()["invoice"]["invoice_id"] == first.json()["invoice"]["invoice_id"]
    assert client.post("/api/invoices/checkout", headers=owner, json={**body, "payment_method": "Orange Money"}).status_code == 409
    assert client.post("/api/invoices/checkout", headers=owner, json={k:v for k,v in body.items() if k != "idempotency_key"}).status_code == 422


def test_concurrent_checkout_has_one_invoice():
    key = uuid4().hex
    def checkout(_):
        return db.checkout_once(1, key, 1, "full_intel_dossier", "Cash", uuid4().hex)[0]["invoice_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(checkout, range(4)))
    assert len(set(results)) == 1
    conn = db.get_db_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM financial_invoices").fetchone()[0] == 1
    finally:
        conn.close()
