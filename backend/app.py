"""
SYTECH DEVICE TRACKING - Central API & Intelligence Engine (Version 4.0)
Full FastAPI Backend integrating:
- PRD 7-table schema
- Automated OSINT & Facial Recognition Cascade
- Technician Hub BSSID Clustering in Gaborone
- The Blurred Paywall UI API & Botswana Mobile Money Checkout
- Official Cybercrime Evidence Affidavit PDF generation
- False-Alarm Master PIN / Remote Token handling
- Real-time WebSocket incident dispatch
"""

import os
import json
import secrets
import asyncio
import time
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Request,
    BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .database.contacts import normalize_contact
from .database import db
from .database.schema import USING_POSTGRES
from . import security
from .services import (
    osint_pipeline,
    technician_hub,
    affidavit_generator,
    ocr_service,
)


app = FastAPI(
    title="SYTECH DEVICE TRACKING API",
    description=(
        "Enterprise Anti-Theft Honeypot & Forensic Intelligence "
        "Recovery Platform (Version 4.0)"
    ),
    version="4.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ACTIVE WEBSOCKET CONNECTIONS
# ============================================================

connected_clients: List[WebSocket] = []


async def broadcast_ws_event(
    event_type: str,
    data: Dict[str, Any],
):
    message = json.dumps(
        {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
    )

    disconnected = []

    for client in connected_clients:
        try:
            account = security.current_user(
                "Bearer " + client.state.auth_token
            )

            if account["role"] not in (
                "admin",
                "operator",
            ):
                raise HTTPException(
                    status_code=403
                )

        except HTTPException:
            await client.close(code=1008)
            disconnected.append(client)
            continue

        try:
            await client.send_text(message)

        except Exception:
            disconnected.append(client)

    for dc in disconnected:
        if dc in connected_clients:
            connected_clients.remove(dc)


# ============================================================
# REQUEST MODELS
# ============================================================

class UserRegisterRequest(BaseModel):
    full_name_omang: str
    primary_contact: str
    alt_contact: str

    password: str = Field(
        min_length=12,
        max_length=128,
    )

    @field_validator("primary_contact")
    @classmethod
    def canonical_contact(cls, value):
        value = normalize_contact(value)

        if not value:
            raise ValueError(
                "Contact is required"
            )

        return value


class DeviceRegisterRequest(BaseModel):
    user_id: int

    device_type: Literal[
        "smartphone",
        "laptop",
    ]

    brand: str
    model: str

    hardware_identifier: str

    purchase_price_bwp: float = Field(
        gt=0,
        allow_inf_nan=False,
    )

    master_backup_pin: str = Field(
        pattern=r"^\d{6,12}$"
    )

    receipt_image_url: Optional[str] = (
        "https://sytech.co.bw/receipts/"
        "sample_mascom_receipt.jpg"
    )

    store_name: Optional[str] = (
        "Orange Botswana - Game City"
    )


class TelemetryIngressRequest(BaseModel):
    device_id: int

    trigger_type: str

    local_failed_attempts: Optional[int] = 0

    captured_ip: Optional[str] = (
        "168.167.12.84"
    )

    captured_network_operator: Optional[str] = (
        "Orange Botswana"
    )

    new_sim_number_imsi: Optional[str] = None
    new_phone_number: Optional[str] = None
    nearby_wifi_macs: Optional[str] = None
    suspect_photo_url: Optional[str] = None

    coarse_latitude: Optional[float] = -24.6580
    coarse_longitude: Optional[float] = 25.9060


class MasterPinVerificationRequest(BaseModel):
    device_id: int
    entered_pin: str


class RemoteResetTokenRequest(BaseModel):
    device_id: int
    reset_token: str


class CheckoutRequest(BaseModel):
    device_id: int

    selected_service: Literal[
        "data_recovery_only",
        "full_intel_dossier",
        "registration_only",
    ]

    payment_method: str

    payer_phone_or_account: Optional[str] = (
        "+267 71 000 000"
    )

    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
    )


class BackupPinUpdateRequest(BaseModel):
    password: str = Field(
        max_length=128
    )

    new_pin: str = Field(
        pattern=r"^[0-9]{6,12}$"
    )


class LoginRequest(BaseModel):
    primary_contact: str

    password: str = Field(
        max_length=128
    )


class RoleUpdateRequest(BaseModel):
    role: str


# ============================================================
# ADMIN BOOTSTRAP
# ============================================================

security.bootstrap_admin_from_environment()


# ============================================================
# HELPERS
# ============================================================

def get_authorized_device(
    device_id: int,
    user: Dict[str, Any],
) -> Dict[str, Any]:

    device = db.get_device(device_id)

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    if (
        user["role"] == "customer"
        and device["user_id"]
        != user["user_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "You may only access "
                "your own devices"
            ),
        )

    return device


def public_device(device):
    """
    Remove the hashed backup PIN before sending
    a device record to the browser.
    """
    return {
        key: value
        for key, value in device.items()
        if key != "master_backup_pin"
    }


def dossier_invoice(device_id):
    conn = db.get_db_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM financial_invoices
            WHERE device_id = ?
              AND selected_service = 'full_intel_dossier'
              AND is_settled = TRUE
            ORDER BY invoice_id DESC
            LIMIT 1
            """,
            (device_id,),
        ).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()


def require_demo():
    if os.getenv("SYTECH_DEMO_MODE") != "1":
        raise HTTPException(
            status_code=503,
            detail=(
                "This integration is simulated. "
                "Enable SYTECH_DEMO_MODE=1 only "
                "for local demonstrations."
            ),
        )


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Normalize PostgreSQL NUMERIC / Decimal values
    before JSON serialization or arithmetic.
    """
    if value is None:
        return default

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


def safe_social_links(value: Any) -> List[str]:
    """
    Safely handle legacy SQLite values and newer
    PostgreSQL values for suspect_social_links.
    """
    if not value:
        return []

    if isinstance(value, list):
        return [
            str(item)
            for item in value
            if item
        ]

    if isinstance(value, tuple):
        return [
            str(item)
            for item in value
            if item
        ]

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return [
                    str(item)
                    for item in parsed
                    if item
                ]

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            return []

    return []


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "system": (
            "SYTECH DEVICE TRACKING v4.0"
        ),
        "market": "Gaborone, Botswana",
        "database": (
            "postgres"
            if USING_POSTGRES
            else "sqlite"
        ),
    }


# ============================================================
# USERS / AUTHENTICATION
# ============================================================

@app.post("/api/users/register")
def register_user(
    req: UserRegisterRequest,
):
    if db.get_user_by_contact(
        req.primary_contact
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this "
                "contact already exists"
            ),
        )

    try:
        user_id = db.create_user(
            req.full_name_omang,
            req.primary_contact,
            req.alt_contact,
            security.hash_password(
                req.password
            ),
        )

    except Exception as exc:
        if exc.__class__.__name__ not in (
            "IntegrityError",
            "UniqueViolation",
        ):
            raise

        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this "
                "contact already exists"
            ),
        )

    return {
        "status": "success",
        "user_id": user_id,
        "full_name_omang":
            req.full_name_omang,
        "role": "customer",
    }


@app.post("/api/auth/login")
def login(
    req: LoginRequest,
    request: Request,
):
    security.limit_attempts(
        (
            "login-ip",
            request.client.host
            if request.client
            else "unknown",
        ),
        limit=30,
    )

    security.limit_attempts(
        (
            "login",
            normalize_contact(
                req.primary_contact
            ),
        ),
        limit=10,
    )

    user = db.get_user_by_contact(
        req.primary_contact
    )

    if (
        not user
        or not security.verify_password(
            req.password,
            user["password_hash"],
        )
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Invalid contact or password"
            ),
        )

    return {
        "access_token":
            security.create_session(
                user["user_id"]
            ),

        "token_type":
            "bearer",

        "user": {
            "user_id":
                user["user_id"],

            "full_name_omang":
                user["full_name_omang"],

            "role":
                user["role"],
        },
    }


@app.post("/api/auth/logout")
def logout(
    request: Request,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    token = (
        request.headers
        .get(
            "authorization",
            "",
        )
        .removeprefix("Bearer ")
    )

    security.SESSIONS.pop(
        token,
        None,
    )

    return {
        "status": "signed_out"
    }


@app.get("/api/auth/me")
def get_current_account(
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    return {
        "user_id":
            user["user_id"],

        "full_name_omang":
            user["full_name_omang"],

        "primary_contact":
            user["primary_contact"],

        "role":
            user["role"],
    }


@app.patch(
    "/api/users/{user_id}/role"
)
def set_user_role(
    user_id: int,
    req: RoleUpdateRequest,
    admin: Dict[str, Any] = Depends(
        security.require_roles("admin")
    ),
):
    if (
        req.role
        not in security.VALID_ROLES
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Role must be customer, "
                "operator, or admin"
            ),
        )

    if not db.get_user(user_id):
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    db.update_user_role(
        user_id,
        req.role,
    )

    return {
        "status": "updated",
        "user_id": user_id,
        "role": req.role,
    }


# ============================================================
# DEVICE REGISTRATION
# ============================================================

@app.post("/api/devices/register")
def register_device(
    req: DeviceRegisterRequest,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    if (
        user["role"] == "customer"
        and req.user_id
        != user["user_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Customers may only register "
                "devices for their own account"
            ),
        )

    owner = db.get_user(
        req.user_id
    )

    if not owner:
        raise HTTPException(
            status_code=404,
            detail="User profile not found",
        )

    device_id = db.register_device(
        user_id=req.user_id,
        device_type=req.device_type,
        brand=req.brand,
        model=req.model,
        hardware_identifier=(
            req.hardware_identifier
        ),
        purchase_price_bwp=(
            req.purchase_price_bwp
        ),
        master_backup_pin=(
            security.hash_password(
                req.master_backup_pin
            )
        ),
    )

    ocr_res = (
        ocr_service
        .process_receipt_verification(
            device_id=device_id,

            receipt_image_url=(
                req.receipt_image_url
                or (
                    "https://sytech.co.bw/"
                    "receipts/"
                    "sample_mascom_receipt.jpg"
                )
            ),

            user_omang_name=(
                owner["full_name_omang"]
            ),

            price_bwp=(
                req.purchase_price_bwp
            ),

            store_name=req.store_name,
        )
    )

    device = db.get_device(
        device_id
    )

    return {
        "status": "success",
        "device_id": device_id,
        "device":
            public_device(device),

        "ocr_verification":
            ocr_res["ocr_result"],
    }


# ============================================================
# DEVICE LIST
# ============================================================

@app.get("/api/devices")
def list_devices(
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    """
    Customers see their own devices.
    Admin/operator accounts see all devices.

    Owner information is added to the public response
    so the dashboard registry can display ownership
    without making a separate request for every card.
    """

    if user["role"] == "customer":
        devices = (
            db.get_devices_for_user(
                user["user_id"]
            )
        )

    else:
        devices = (
            db.get_all_devices()
        )

    results = []

    for device in devices:
        item = public_device(
            device
        )

        owner = db.get_user(
            device["user_id"]
        )

        if owner:
            item["full_name_omang"] = (
                owner.get(
                    "full_name_omang"
                )
            )

            item[
                "owner_primary_contact"
            ] = owner.get(
                "primary_contact"
            )

        results.append(item)

    return results


# ============================================================
# DEVICE DETAILS
# ============================================================

@app.get(
    "/api/devices/{device_id}"
)
def get_device_details(
    device_id: int,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    device = get_authorized_device(
        device_id,
        user,
    )

    owner = db.get_user(
        device["user_id"]
    )

    intel = (
        db.get_all_intel_for_device(
            device_id
        )
        if (
            user["role"] != "customer"
            or dossier_invoice(
                device_id
            )
        )
        else []
    )

    latest_inv = (
        db.get_latest_invoice_for_device(
            device_id
        )
    )

    owner_payload = None

    if owner:
        owner_payload = {
            key: owner[key]
            for key in (
                "user_id",
                "full_name_omang",
                "primary_contact",
            )
        }

    return {
        "device":
            public_device(device),

        "user":
            owner_payload,

        "intel_logs":
            intel,

        "latest_invoice":
            latest_inv,
    }


# ============================================================
# TELEMETRY
# ============================================================

@app.post("/api/telemetry/ingress")
async def ingest_telemetry(
    req: TelemetryIngressRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(
        security.require_roles(
            "operator",
            "admin",
        )
    ),
):
    """
    Core Telemetry Ingress.

    Receives demo triggers from TrapPhon / TrapLap
    and runs the simulated enrichment pipeline.
    """

    require_demo()

    device = db.get_device(
        req.device_id
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    new_status = (
        "pinged_enriching"
    )

    if (
        req.trigger_type
        == "failed_login"
    ):
        new_status = (
            "locally_compromised_offline"
        )

    elif req.trigger_type in (
        "sim_swap",
        "wifi_captive_connect",
    ):
        new_status = (
            "pinged_enriching"
        )

    db.update_device_status(
        req.device_id,
        new_status,
    )

    intel_id = (
        db.log_tracking_intel(
            device_id=req.device_id,

            trigger_type=(
                req.trigger_type
            ),

            local_failed_attempts=(
                req.local_failed_attempts
                or 0
            ),

            captured_ip=(
                req.captured_ip
            ),

            captured_network_operator=(
                req.captured_network_operator
            ),

            new_sim_number_imsi=(
                req.new_sim_number_imsi
            ),

            new_phone_number=(
                req.new_phone_number
            ),

            nearby_wifi_macs=(
                req.nearby_wifi_macs
            ),

            suspect_photo_url=(
                req.suspect_photo_url
            ),

            coarse_latitude=(
                req.coarse_latitude
            ),

            coarse_longitude=(
                req.coarse_longitude
            ),
        )
    )

    enrichment = (
        osint_pipeline
        .execute_osint_cascade(
            device_id=req.device_id,
            intel_id=intel_id,

            phone_number=(
                req.new_phone_number
            ),

            photo_url=(
                req.suspect_photo_url
            ),
        )
    )

    await broadcast_ws_event(
        "TELEMETRY_INGRESS",
        {
            "device_id":
                req.device_id,

            "trigger_type":
                req.trigger_type,

            "new_status":
                "ready",

            "enrichment":
                enrichment,
        },
    )

    return {
        "simulated": True,

        "status":
            "received_and_enriched",

        "intel_id":
            intel_id,

        "enrichment":
            enrichment,
    }


# ============================================================
# FALSE ALARM MANAGEMENT
# ============================================================

@app.post(
    "/api/devices/{device_id}/verify-master-pin"
)
async def verify_master_pin(
    device_id: int,
    req: MasterPinVerificationRequest,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    """
    Owner demo reset using the backup PIN.
    """

    device = get_authorized_device(
        device_id,
        user,
    )

    security.limit_attempts(
        (
            "pin",
            device_id,
        )
    )

    correct_pin = (
        device.get(
            "master_backup_pin"
        )
        or ""
    )

    if not correct_pin.startswith(
        "pbkdf2_sha256$"
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Choose a new backup PIN "
                "using your account password "
                "before resetting this device."
            ),
        )

    if security.verify_password(
        req.entered_pin.strip(),
        correct_pin,
    ):
        db.log_false_alarm(
            device_id=device_id,

            cleared_via_method=(
                "local_passphrase"
            ),

            attempts_before_clear=3,
        )

        await broadcast_ws_event(
            "FALSE_ALARM_CLEARED",
            {
                "device_id":
                    device_id,

                "method":
                    "local_passphrase",
            },
        )

        return {
            "status": "cleared",

            "message": (
                "Demo device marked as secured. "
                "No real device was changed."
            ),
        }

    raise HTTPException(
        status_code=403,
        detail=(
            "Invalid Master Backup PIN. "
            "Lockdown remains active."
        ),
    )


@app.put(
    "/api/devices/{device_id}/backup-pin"
)
def update_backup_pin(
    device_id: int,
    req: BackupPinUpdateRequest,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    device = get_authorized_device(
        device_id,
        user,
    )

    if (
        device["user_id"]
        != user["user_id"]
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the device owner can "
                "change its backup PIN"
            ),
        )

    security.limit_attempts(
        (
            "pin-change",
            user["user_id"],
        )
    )

    if not security.verify_password(
        req.password,
        user["password_hash"],
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Incorrect account password"
            ),
        )

    conn = db.get_db_connection()

    try:
        conn.execute(
            """
            UPDATE devices
            SET master_backup_pin=?
            WHERE device_id=?
            """,
            (
                security.hash_password(
                    req.new_pin
                ),
                device_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()

    return {
        "status": "updated"
    }


# ============================================================
# REMOTE RESET TOKEN
# ============================================================

ACTIVE_RESET_TOKENS: Dict[
    int,
    tuple,
] = {}


@app.post(
    "/api/devices/{device_id}/generate-remote-token"
)
def generate_remote_token(
    device_id: int,
    user: Dict[str, Any] = Depends(
        security.require_roles(
            "operator",
            "admin",
        )
    ),
):
    get_authorized_device(
        device_id,
        user,
    )

    token = (
        secrets.token_hex(3)
        .upper()
    )

    ACTIVE_RESET_TOKENS[
        device_id
    ] = (
        token,
        time.time() + 600,
    )

    return {
        "status":
            "token_generated",

        "device_id":
            device_id,

        "remote_token":
            token,
    }


@app.post(
    "/api/devices/{device_id}/apply-remote-token"
)
async def apply_remote_token(
    device_id: int,
    req: RemoteResetTokenRequest,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    get_authorized_device(
        device_id,
        user,
    )

    security.limit_attempts(
        (
            "remote-reset",
            device_id,
        )
    )

    stored_token = (
        ACTIVE_RESET_TOKENS.get(
            device_id
        )
    )

    if (
        not stored_token
        or stored_token[1]
        <= time.time()
        or not secrets.compare_digest(
            stored_token[0],
            req.reset_token
            .strip()
            .upper(),
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Invalid or expired "
                "remote reset token"
            ),
        )

    del ACTIVE_RESET_TOKENS[
        device_id
    ]

    db.log_false_alarm(
        device_id=device_id,

        cleared_via_method=(
            "remote_token"
        ),

        attempts_before_clear=3,
    )

    await broadcast_ws_event(
        "FALSE_ALARM_CLEARED",
        {
            "device_id":
                device_id,

            "method":
                "remote_token",
        },
    )

    return {
        "status": "cleared",

        "message": (
            "Remote token validated. "
            "Device returned to SECURED state."
        ),
    }


# ============================================================
# PAYWALL HELPERS
# ============================================================

def mask_name(
    name: str,
) -> str:

    parts = name.split()

    masked_parts = []

    for part in parts:

        if not part:
            continue

        if len(part) <= 2:
            masked_parts.append(
                part[0] + "*"
            )

        else:
            masked_parts.append(
                part[:2]
                + "*"
                * (
                    len(part) - 2
                )
            )

    return " ".join(
        masked_parts
    )


def mask_phone(
    phone: str,
) -> str:

    if not phone:
        return "+267 7* *** **"

    if len(phone) < 8:
        return "+267 7* *** **"

    return (
        phone[:6]
        + " **** "
        + phone[-2:]
    )


# ============================================================
# DEVICE PREVIEW
# ============================================================

@app.get(
    "/api/devices/{device_id}/preview"
)
def get_device_paywall_preview(
    device_id: int,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    """
    Blurred Preview Interface.

    PostgreSQL NUMERIC values are normalized to
    Python floats before arithmetic. This prevents
    Decimal + float TypeError failures.
    """

    device = get_authorized_device(
        device_id,
        user,
    )

    intel = db.get_latest_intel(
        device_id
    )

    latest_inv = dossier_invoice(
        device_id
    )

    is_settled = bool(
        latest_inv
        and latest_inv[
            "is_settled"
        ]
    )


    # --------------------------------------------------------
    # POSTGRES / SUPABASE MONEY NORMALIZATION
    # --------------------------------------------------------

    purchase_price = safe_float(
        device.get(
            "purchase_price_bwp"
        )
    )

    success_fee = safe_float(
        device.get(
            "success_fee_calculated"
        )
    )

    is_registration_paid = bool(
        device.get(
            "is_registration_paid"
        )
    )

    deferred_reg_amount = (
        0.0
        if is_registration_paid
        else 50.0
    )

    data_recovery_fee = 50.0

    option_a_total = round(
        success_fee
        + deferred_reg_amount,
        2,
    )

    option_b_total = round(
        data_recovery_fee
        + deferred_reg_amount,
        2,
    )


    # --------------------------------------------------------
    # NO TELEMETRY
    # --------------------------------------------------------

    if not intel:
        return {
            "status":
                "no_telemetry_yet",

            "device":
                public_device(
                    device
                ),

            "is_settled":
                is_settled,

            "pricing": {
                "verified_purchase_price":
                    purchase_price,

                "deferred_reg_fee":
                    deferred_reg_amount,

                "option_a_dossier": {
                    "title":
                        (
                            "Option A: Full "
                            "Intel Dossier Fee"
                        ),

                    "description":
                        (
                            "Unlocks simulated results "
                            "and a demonstration report. "
                            "No identity is verified."
                        ),

                    "base_fee":
                        success_fee,

                    "deferred_reg_fee":
                        deferred_reg_amount,

                    "total_due":
                        option_a_total,
                },

                "option_b_data_recovery": {
                    "title":
                        (
                            "Option B: Data "
                            "Recovery Only Fee"
                        ),

                    "description":
                        (
                            "Demonstration pricing only. "
                            "Data recovery and remote wipe "
                            "are not implemented."
                        ),

                    "base_fee":
                        data_recovery_fee,

                    "deferred_reg_fee":
                        deferred_reg_amount,

                    "total_due":
                        option_b_total,
                },
            },
        }


    # --------------------------------------------------------
    # TELEMETRY EXISTS
    # --------------------------------------------------------

    suspect_name = (
        intel.get(
            "suspect_name_alias"
        )
        or "Thatayaone Motlhanka"
    )

    phone_number = (
        intel.get(
            "new_phone_number"
        )
        or "+26771234567"
    )

    carrier = (
        intel.get(
            "captured_network_operator"
        )
        or "Orange Botswana"
    )

    photo_url = (
        intel.get(
            "suspect_photo_url"
        )
        or (
            "https://images.unsplash.com/"
            "photo-1507003211169-"
            "0a1dd7228f2d?"
            "w=400&fit=crop&q=80"
        )
    )


    # --------------------------------------------------------
    # SETTLED DOSSIER
    # --------------------------------------------------------

    if is_settled:

        social_links = (
            safe_social_links(
                intel.get(
                    "suspect_social_links"
                )
            )
        )

        return {
            "device":
                public_device(
                    device
                ),

            "is_settled":
                True,

            "settled_service":
                latest_inv[
                    "selected_service"
                ],

            "suspect_name":
                suspect_name,

            "phone_number":
                phone_number,

            "carrier":
                carrier,

            "imsi":
                intel.get(
                    "new_sim_number_imsi"
                ),

            "photo_url":
                photo_url,

            "social_links":
                social_links,

            "ip_address":
                intel.get(
                    "captured_ip"
                ),

            "wifi_bssid":
                intel.get(
                    "nearby_wifi_macs"
                ),

            "latitude":
                safe_float(
                    intel.get(
                        "coarse_latitude"
                    )
                )
                if intel.get(
                    "coarse_latitude"
                ) is not None
                else None,

            "longitude":
                safe_float(
                    intel.get(
                        "coarse_longitude"
                    )
                )
                if intel.get(
                    "coarse_longitude"
                ) is not None
                else None,

            "pdf_affidavit_url":
                (
                    f"/api/devices/"
                    f"{device_id}/"
                    "affidavit-pdf"
                ),

            "invoice":
                latest_inv,
        }


    # --------------------------------------------------------
    # UNSETTLED / BLURRED PAYWALL
    # --------------------------------------------------------

    return {
        "device":
            public_device(
                device
            ),

        "is_settled":
            False,

        "device_brand":
            device["brand"],

        "device_model":
            device["model"],

        "hardware_identifier":
            device[
                "hardware_identifier"
            ],

        "suspect_name_masked":
            mask_name(
                suspect_name
            ),

        "phone_number_masked":
            mask_phone(
                phone_number
            ),

        "carrier":
            carrier,

        "photo_blurred":
            True,

        # Do not expose original evidence image
        # before entitlement.
        "photo_url":
            "",

        "pricing": {

            "verified_purchase_price":
                purchase_price,

            "deferred_reg_fee":
                deferred_reg_amount,

            "option_a_dossier": {

                "title":
                    (
                        "Option A: Full "
                        "Intel Dossier Fee"
                    ),

                "description":
                    (
                        "Unlocks simulated results "
                        "and a demonstration report. "
                        "No identity is verified."
                    ),

                "base_fee":
                    success_fee,

                "deferred_reg_fee":
                    deferred_reg_amount,

                "total_due":
                    option_a_total,
            },

            "option_b_data_recovery": {

                "title":
                    (
                        "Option B: Data "
                        "Recovery Only Fee"
                    ),

                "description":
                    (
                        "Demonstration pricing only. "
                        "Data recovery and remote wipe "
                        "are not implemented."
                    ),

                "base_fee":
                    data_recovery_fee,

                "deferred_reg_fee":
                    deferred_reg_amount,

                "total_due":
                    option_b_total,
            },
        },
    }


# ============================================================
# CHECKOUT
# ============================================================

@app.post("/api/invoices/checkout")
async def checkout_service(
    req: CheckoutRequest,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    get_authorized_device(
        req.device_id,
        user,
    )

    require_demo()

    """
    Creates and settles an invoice using the
    simulated Botswana payment gateway.
    """

    payment_name = (
        req.payment_method.lower()
    )

    if "orange" in payment_name:
        prefix = "OM"

    elif "myzaka" in payment_name:
        prefix = "MZ"

    else:
        prefix = "SM"

    gateway_ref = (
        f"{prefix}-BW-"
        f"{secrets.token_hex(4).upper()}"
    )

    try:
        settled_inv, replayed = (
            db.checkout_once(
                user["user_id"],
                req.idempotency_key,
                req.device_id,
                req.selected_service,
                req.payment_method,
                gateway_ref,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    if not replayed:
        await broadcast_ws_event(
            "INVOICE_SETTLED",
            {
                "device_id":
                    req.device_id,

                "selected_service":
                    req.selected_service,

                "total_due":
                    safe_float(
                        settled_inv[
                            "total_due"
                        ]
                    ),

                "gateway_reference":
                    settled_inv[
                        "gateway_reference"
                    ],
            },
        )

    # Normalize monetary values before returning
    # PostgreSQL Decimal values to FastAPI.

    invoice_payload = dict(
        settled_inv
    )

    for money_field in (
        "amount_due",
        "registration_fee_due",
        "total_due",
    ):
        if (
            money_field
            in invoice_payload
            and invoice_payload[
                money_field
            ] is not None
        ):
            invoice_payload[
                money_field
            ] = safe_float(
                invoice_payload[
                    money_field
                ]
            )

    return {
        "status":
            "success",

        "message":
            (
                "Simulated payment only; "
                "no funds were transferred."
            ),

        "simulated":
            True,

        "invoice":
            invoice_payload,

        "pdf_affidavit_ready":
            (
                req.selected_service
                == "full_intel_dossier"
            ),

        "download_url":
            (
                f"/api/devices/"
                f"{req.device_id}/"
                "affidavit-pdf"
            ),
    }


# ============================================================
# PDF REPORT
# ============================================================

@app.get(
    "/api/devices/{device_id}/affidavit-pdf"
)
def download_affidavit_pdf(
    device_id: int,
    user: Dict[str, Any] = Depends(
        security.current_user
    ),
):
    get_authorized_device(
        device_id,
        user,
    )

    if not dossier_invoice(
        device_id
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Full dossier entitlement "
                "required"
            ),
        )

    pdf_path = (
        affidavit_generator
        .generate_police_affidavit_pdf(
            device_id
        )
    )

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=(
            f"SYTECH_DEMO_REPORT_"
            f"{device_id}.pdf"
        ),
    )


# ============================================================
# TECHNICIAN HUBS
# ============================================================

@app.get("/api/technician-hubs")
def get_technician_hubs(
    user: Dict[str, Any] = Depends(
        security.require_roles(
            "operator",
            "admin",
        )
    ),
):
    hubs = (
        technician_hub
        .analyze_bssid_clusters()
    )

    return {
        "total_flagged_hubs":
            len(hubs),

        "hubs":
            hubs,
    }


# ============================================================
# WEBSOCKET FEED
# ============================================================

@app.websocket("/ws/feed")
async def websocket_endpoint(
    websocket: WebSocket,
):
    await websocket.accept()

    try:
        token = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=5,
        )

        user = security.current_user(
            "Bearer " + token
        )

        if user["role"] not in (
            "admin",
            "operator",
        ):
            raise HTTPException(
                status_code=403
            )

    except Exception:
        await websocket.close(
            code=1008
        )
        return

    websocket.state.auth_token = (
        token
    )

    connected_clients.append(
        websocket
    )

    await websocket.send_json(
        {
            "event":
                "AUTHENTICATED"
        }
    )

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(
                websocket
            )


# ============================================================
# FRONTEND DASHBOARD
# ============================================================

DASHBOARD_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            __file__
        )
    ),
    "dashboard",
    "public",
)


if os.path.exists(
    DASHBOARD_DIR
):
    app.mount(
        "/dashboard",
        StaticFiles(
            directory=DASHBOARD_DIR,
            html=True,
        ),
        name="dashboard",
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "message": (
            "Welcome to SYTECH DEVICE TRACKING "
            "v4.0 API. Visit /dashboard/ for "
            "Operator & Client Portal."
        )
    }