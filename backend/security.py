"""Local account authentication for the SYTECH prototype.

Sessions are intentionally in-memory for this single-server deployment. A production
deployment should replace this with an audited identity/session provider.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time
import threading
import math
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException

from .database import db

ITERATIONS = 310_000
SESSIONS: Dict[str, tuple] = {}
VALID_ROLES = {"customer", "operator", "admin"}
ATTEMPTS = {}
_attempt_lock = threading.Lock()


def limit_attempts(key, limit=5, window=900):
    """Bounded, process-local throttling for this single-server prototype."""
    now = time.monotonic()
    with _attempt_lock:
        for expired in [k for k, (_, until) in ATTEMPTS.items() if until <= now]:
            del ATTEMPTS[expired]
        count, until = ATTEMPTS.get(key, (0, now + window))
        if count >= limit or (key not in ATTEMPTS and len(ATTEMPTS) >= 10000):
            raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.", headers={"Retry-After": str(max(1, math.ceil(until - now)))})
        ATTEMPTS[key] = (count + 1, until)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations))
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (user_id, time.time() + 28800)
    return token

def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.removeprefix("Bearer ")
    session = SESSIONS.get(token)
    if session and session[1] <= time.time():
        SESSIONS.pop(token, None)
        session = None
    user_id = session[0] if session else None
    user = db.get_user(user_id) if user_id else None
    if not user:
        raise HTTPException(status_code=401, detail="Session is invalid or expired")
    return user

def require_roles(*roles: str):
    def checker(user: dict = Depends(current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="This action is not permitted for your role")
        return user
    return checker

def bootstrap_admin_from_environment() -> bool:
    if db.has_admin_user():
        return False
    password = os.getenv("SYTECH_ADMIN_PASSWORD", "")
    contact = os.getenv("SYTECH_ADMIN_CONTACT", "")
    name = os.getenv("SYTECH_ADMIN_NAME", "System Administrator")
    if len(password) < 12 or not contact:
        return False
    db.create_user(name, contact, contact, hash_password(password), role="admin")
    return True
