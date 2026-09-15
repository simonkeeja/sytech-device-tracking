"""
SYTECH OSINT & Intelligence Pipeline (Version 4.0)
Automated Intelligence Cascade:
1. Financial Name Lookup (Orange Money, MyZaka, Smega KYC)
2. Facial Recognition & Reverse-Image Indexing (PimEye, FaceCheck.ID, WhatsApp Avatar / Webcam)
3. Social Footprint Aggregation (Facebook, Instagram, LinkedIn, secondary numbers)
"""
import time
import random
import json
from typing import Dict, Any, List, Optional
from ..database import db

# Simulated Botswana Mobile Money KYC Database
BOTSWANA_KYC_REGISTRY = {
    "+26771234567": {"name": "Thatayaone Motlhanka", "carrier": "Orange Botswana", "wallet": "Orange Money"},
    "+26772345678": {"name": "Kabo Kgosietsile", "carrier": "Mascom Wireless", "wallet": "MyZaka"},
    "+26773456789": {"name": "Tumelo Sebego", "carrier": "BTC Mobile", "wallet": "Smega"},
    "+26774567890": {"name": "Mphoeng Ditshupo", "carrier": "Orange Botswana", "wallet": "Orange Money"},
    "+26775678901": {"name": "Goitsemodimo Phiri", "carrier": "Mascom Wireless", "wallet": "MyZaka"},
}

BOTSWANA_SUSPECT_POOLS = [
    {"name": "Thatayaone Motlhanka", "alias": "DJ Sparks Gabs", "social": ["https://facebook.com/thatayaone.motlhanka.gabs", "https://instagram.com/dj_sparks_bw"]},
    {"name": "Kabo Kgosietsile", "alias": "Kabo_Tech_Fix", "social": ["https://facebook.com/kabo.kgosietsile.gabs", "https://linkedin.com/in/kabo-kgosietsile-bw"]},
    {"name": "Tumelo Sebego", "alias": "T-Man Botswana", "social": ["https://facebook.com/tumelo.sebego.7", "https://instagram.com/tman_bw_official"]},
    {"name": "Mphoeng Ditshupo", "alias": "Mphoeng_Electronics", "social": ["https://facebook.com/mphoeng.ditshupo", "https://instagram.com/mphoeng_bw"]},
]

def lookup_financial_kyc(phone_number: str) -> Dict[str, str]:
    """
    Feeds target cell number into simulated Botswana Mobile Money gateways:
    Orange Money, MyZaka, Smega to extract official KYC-registered legal name.
    """
    clean_num = phone_number.replace(" ", "").replace("-", "")
    if not clean_num.startswith("+267"):
        if clean_num.startswith("7") and len(clean_num) == 8:
            clean_num = "+267" + clean_num
        elif clean_num.startswith("267"):
            clean_num = "+" + clean_num

    if clean_num in BOTSWANA_KYC_REGISTRY:
        return BOTSWANA_KYC_REGISTRY[clean_num]

    # Generate a deterministic realistic Botswana KYC identity if not in predefined registry
    hash_val = sum(ord(c) for c in clean_num)
    suspect = BOTSWANA_SUSPECT_POOLS[hash_val % len(BOTSWANA_SUSPECT_POOLS)]
    carrier = "Orange Botswana" if "72" in clean_num or "74" in clean_num else ("Mascom Wireless" if "71" in clean_num or "75" in clean_num else "BTC Mobile")
    wallet = "Orange Money" if carrier == "Orange Botswana" else ("MyZaka" if carrier == "Mascom Wireless" else "Smega")

    return {
        "name": suspect["name"],
        "carrier": carrier,
        "wallet": wallet,
        "alias": suspect["alias"],
        "social": suspect["social"]
    }

def run_reverse_face_indexing(photo_url: str, seed_name: str) -> List[Dict[str, Any]]:
    """
    Processes face vector through reverse-image indexers (PimEye, FaceCheck.ID, WhatsApp Avatar).
    """
    matches = [
        {
            "source_url": "https://facecheck.id/results/bw_match_" + str(random.randint(10000, 99999)),
            "confidence_score": round(random.uniform(91.5, 98.8), 2),
            "resolved_name": seed_name,
            "resolved_email": seed_name.lower().replace(" ", ".") + "@gmail.com",
            "resolved_phone_link": "+267 7" + str(random.randint(1000000, 9999999))
        },
        {
            "source_url": "https://pimeye.ai/index/match/botswana_" + str(random.randint(1000, 9999)),
            "confidence_score": round(random.uniform(84.0, 92.0), 2),
            "resolved_name": seed_name,
            "resolved_email": seed_name.lower().replace(" ", "") + "@yahoo.com",
            "resolved_phone_link": None
        }
    ]
    return matches

def execute_osint_cascade(device_id: int, intel_id: int, phone_number: Optional[str] = None, photo_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes the complete OSINT cascade for an ingressed event:
    1. Mobile Money KYC Name Extraction
    2. Face recognition indexing
    3. Social footprint mapping
    4. Stores results in tracking_intel & face_search_results tables
    5. Transitions device status to 'ready' for blurred preview
    """
    # 1. Financial Name Lookup
    target_num = phone_number or "+26771234567"
    kyc_info = lookup_financial_kyc(target_num)
    resolved_name = kyc_info["name"]
    carrier = kyc_info["carrier"]
    alias = kyc_info.get("alias", "Unknown_Alias")
    social_links = kyc_info.get("social", [
        f"https://facebook.com/{resolved_name.lower().replace(' ', '.')}",
        f"https://instagram.com/{resolved_name.lower().replace(' ', '_')}"
    ])

    default_photo = photo_url or "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&fit=crop&q=80"

    # 2. Update tracking_intel record
    conn = db.get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE tracking_intel
        SET suspect_name_alias = ?,
            suspect_social_links = ?,
            suspect_photo_url = ?,
            captured_network_operator = COALESCE(captured_network_operator, ?)
        WHERE intel_id = ?
        """,
        (resolved_name, json.dumps(social_links), default_photo, carrier, intel_id)
    )
    conn.commit()
    conn.close()

    # 3. Facial recognition search tracks
    face_matches = run_reverse_face_indexing(default_photo, resolved_name)
    for match in face_matches:
        db.add_face_search_result(
            intel_id=intel_id,
            scraped_source_url=match["source_url"],
            confidence_score=match["confidence_score"],
            resolved_full_name=match["resolved_name"],
            resolved_email=match["resolved_email"],
            resolved_phone_link=match["resolved_phone_link"]
        )

    # 4. Advance device state to 'ready' (ready for blurred preview / contingency invoice)
    db.update_device_status(device_id, "ready")

    return {
        "status": "enriched",
        "intel_id": intel_id,
        "device_id": device_id,
        "suspect_name": resolved_name,
        "carrier": carrier,
        "wallet": kyc_info.get("wallet"),
        "social_links": social_links,
        "photo_url": default_photo,
        "face_matches_count": len(face_matches)
    }
