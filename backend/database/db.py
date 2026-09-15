"""
Database helper module for SYTECH DEVICE TRACKING v4.0.
Provides unified access methods for all 7 database tables.
All connections are strictly protected with try/finally to prevent database locking.
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from .schema import get_db_connection, init_db
from .contacts import normalize_contact

# Ensure tables exist
init_db()

def create_user(full_name_omang: str, primary_contact: str, alt_contact: str, password_hash: str, role: str = "customer") -> int:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (full_name_omang, primary_contact, alt_contact, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (full_name_omang, normalize_contact(primary_contact), alt_contact, password_hash, role)
        )
        user_id = c.lastrowid
        conn.commit()
        return user_id
    finally:
        conn.close()

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_contact(primary_contact: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE primary_contact = ?", (normalize_contact(primary_contact),))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def has_admin_user() -> bool:
    conn = get_db_connection()
    try:
        return conn.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1").fetchone() is not None
    finally:
        conn.close()

def update_user_role(user_id: int, role: str) -> None:
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
        conn.commit()
    finally:
        conn.close()

def register_device(
    user_id: int,
    device_type: str,
    brand: str,
    model: str,
    hardware_identifier: str,
    purchase_price_bwp: float,
    master_backup_pin: str = "7924"
) -> int:
    # Contingency fee is strictly 25% of verified purchase price
    success_fee_calculated = round(purchase_price_bwp * 0.25, 2)
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO devices (
                user_id, device_type, brand, model, hardware_identifier,
                purchase_price_bwp, success_fee_calculated, master_backup_pin, current_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'secured')
            """,
            (user_id, device_type, brand, model, hardware_identifier, purchase_price_bwp, success_fee_calculated, master_backup_pin)
        )
        device_id = c.lastrowid
        conn.commit()
        return device_id
    finally:
        conn.close()

def get_device(device_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_devices() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT d.*, u.full_name_omang, u.primary_contact FROM devices d JOIN users u ON d.user_id = u.user_id ORDER BY d.device_id DESC")
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_devices_for_user(user_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT d.*, u.full_name_omang, u.primary_contact FROM devices d JOIN users u ON d.user_id = u.user_id WHERE d.user_id = ? ORDER BY d.device_id DESC", (user_id,))
        return [dict(r) for r in c.fetchall()]
    finally:
        conn.close()

def update_device_status(device_id: int, status: str):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE devices SET current_status = ? WHERE device_id = ?", (status, device_id))
        conn.commit()
    finally:
        conn.close()

def add_receipt(device_id: int, receipt_image_url: str, extracted_store_name: str, extracted_price_bwp: float, is_verified: bool = False, verified_by_operator_id: Optional[int] = None) -> int:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO receipts (device_id, receipt_image_url, extracted_store_name, extracted_price_bwp, is_verified, verified_by_operator_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (device_id, receipt_image_url, extracted_store_name, extracted_price_bwp, bool(is_verified), verified_by_operator_id)
        )
        receipt_id = c.lastrowid
        conn.commit()
        return receipt_id
    finally:
        conn.close()

def log_tracking_intel(
    device_id: int,
    trigger_type: str,
    local_failed_attempts: int = 0,
    captured_ip: Optional[str] = None,
    captured_network_operator: Optional[str] = None,
    new_sim_number_imsi: Optional[str] = None,
    new_phone_number: Optional[str] = None,
    nearby_wifi_macs: Optional[str] = None,
    suspect_name_alias: Optional[str] = None,
    suspect_social_links: Optional[str] = None,
    suspect_photo_url: Optional[str] = None,
    coarse_latitude: Optional[float] = None,
    coarse_longitude: Optional[float] = None
) -> int:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO tracking_intel (
                device_id, trigger_type, local_failed_attempts_logged, captured_ip,
                captured_network_operator, new_sim_number_imsi, new_phone_number,
                nearby_wifi_macs, suspect_name_alias, suspect_social_links,
                suspect_photo_url, coarse_latitude, coarse_longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id, trigger_type, local_failed_attempts, captured_ip,
                captured_network_operator, new_sim_number_imsi, new_phone_number,
                nearby_wifi_macs, suspect_name_alias, suspect_social_links,
                suspect_photo_url, coarse_latitude, coarse_longitude
            )
        )
        intel_id = c.lastrowid
        conn.commit()
        return intel_id
    finally:
        conn.close()

def get_latest_intel(device_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM tracking_intel WHERE device_id = ? ORDER BY intel_id DESC LIMIT 1", (device_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_intel_for_device(device_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM tracking_intel WHERE device_id = ? ORDER BY intel_id DESC", (device_id,))
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def add_face_search_result(
    intel_id: int,
    scraped_source_url: str,
    confidence_score: float,
    resolved_full_name: Optional[str] = None,
    resolved_email: Optional[str] = None,
    resolved_phone_link: Optional[str] = None
) -> int:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO face_search_results (
                intel_id, scraped_source_url, confidence_score, resolved_full_name,
                resolved_email, resolved_phone_link
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (intel_id, scraped_source_url, confidence_score, resolved_full_name, resolved_email, resolved_phone_link)
        )
        match_id = c.lastrowid
        conn.commit()
        return match_id
    finally:
        conn.close()

def get_face_search_results(intel_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM face_search_results WHERE intel_id = ?", (intel_id,))
        rows = c.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def log_false_alarm(device_id: int, cleared_via_method: str, attempts_before_clear: int) -> int:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO false_alarm_logs (device_id, cleared_via_method, attempts_before_clear) VALUES (?, ?, ?)",
            (device_id, cleared_via_method, attempts_before_clear)
        )
        log_id = c.lastrowid
        c.execute("UPDATE devices SET current_status = 'secured' WHERE device_id = ?", (device_id,))
        conn.commit()
        return log_id
    finally:
        conn.close()

def create_financial_invoice(
    device_id: int,
    selected_service: str, # 'registration_only', 'data_recovery_only', 'full_intel_dossier'
    _conn=None,
) -> Dict[str, Any]:
    conn = _conn if _conn is not None else get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
        dev = c.fetchone()
        if not dev:
            raise ValueError(f"Device {device_id} not found")

        device_dict = dict(dev)
        # Check if deferred registration fee is due (P50.00 if is_registration_paid is False)
        deferred_reg_amount = 0.0 if device_dict["is_registration_paid"] else 50.0

        if selected_service == "data_recovery_only":
            base_amount = 50.00
        elif selected_service == "full_intel_dossier":
            base_amount = device_dict["success_fee_calculated"] # 25% of verified receipt
        elif selected_service == "registration_only":
            base_amount = 50.00
            deferred_reg_amount = 0.0
        else:
            raise ValueError(f"Unknown service: {selected_service}")

        total_due = round(base_amount + deferred_reg_amount, 2)

        c.execute(
            """
            INSERT INTO financial_invoices (device_id, selected_service, base_amount, deferred_reg_amount, total_due, is_settled)
            VALUES (?, ?, ?, ?, ?, FALSE)
            """,
            (device_id, selected_service, base_amount, deferred_reg_amount, total_due)
        )
        invoice_id = c.lastrowid
        if _conn is None:
            conn.commit()

        return {
            "invoice_id": invoice_id,
            "device_id": device_id,
            "selected_service": selected_service,
            "base_amount": base_amount,
            "deferred_reg_amount": deferred_reg_amount,
            "total_due": total_due,
            "is_settled": False
        }
    finally:
        if _conn is None:
            conn.close()

def settle_invoice(invoice_id: int, payment_method: str, gateway_reference: str, _conn=None) -> Dict[str, Any]:
    conn = _conn if _conn is not None else get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM financial_invoices WHERE invoice_id = ?", (invoice_id,))
        inv = c.fetchone()
        if not inv:
            raise ValueError(f"Invoice {invoice_id} not found")

        settled_at = datetime.now().isoformat()
        c.execute(
            """
            UPDATE financial_invoices
            SET is_settled = TRUE, payment_method = ?, gateway_reference = ?, settled_at = ?
            WHERE invoice_id = ?
            """,
            (payment_method, gateway_reference, settled_at, invoice_id)
        )

        inv_dict = dict(inv)
        device_id = inv_dict["device_id"]
        if inv_dict["deferred_reg_amount"] > 0 or inv_dict["selected_service"] == "registration_only":
            c.execute("UPDATE devices SET is_registration_paid = TRUE WHERE device_id = ?", (device_id,))

        if _conn is None:
            conn.commit()

        inv_dict["is_settled"] = True
        inv_dict["payment_method"] = payment_method
        inv_dict["gateway_reference"] = gateway_reference
        inv_dict["settled_at"] = settled_at
        return inv_dict
    finally:
        if _conn is None:
            conn.close()


def checkout_once(user_id, request_key, device_id, selected_service, payment_method, gateway_reference):
    payload = json.dumps([device_id, selected_service, payment_method])
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute("SELECT * FROM checkout_requests WHERE user_id=? AND request_key=?", (user_id, request_key)).fetchone()
        if previous:
            if previous["request_payload"] != payload:
                raise ValueError("This checkout key was already used for different details")
            return dict(conn.execute("SELECT * FROM financial_invoices WHERE invoice_id=?", (previous["invoice_id"],)).fetchone()), True
        invoice = create_financial_invoice(device_id, selected_service, _conn=conn)
        settled = settle_invoice(invoice["invoice_id"], payment_method, gateway_reference, _conn=conn)
        conn.execute("INSERT INTO checkout_requests VALUES (?, ?, ?, ?)", (user_id, request_key, payload, invoice["invoice_id"]))
        conn.commit()
        return settled, False
    finally:
        conn.close()

def get_latest_invoice_for_device(device_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM financial_invoices WHERE device_id = ? ORDER BY invoice_id DESC LIMIT 1", (device_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
