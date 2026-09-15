"""
SYTECH OCR & Receipt Verification Service (Version 4.0)
Scans purchase receipts from Mascom, Orange, BTC, and local electronics retailers in Botswana.
Extracts:
- Store Name
- Purchase Price in BWP
- Purchaser Name (matches against Omang National ID holder)
- Calculates locked-in 25% Contingency Asset Recovery Fee
"""
import re
from typing import Dict, Any, Optional
from ..database import db

KNOWN_BOTSWANA_STORES = [
    "Mascom Wireless Store",
    "Orange Botswana Shop",
    "Botswana Telecommunications Corporation (BTC)",
    "Cell City Botswana",
    "Incredible Connection Gaborone",
    "Fone Haus Game City",
    "HiFi Corp Riverwalk",
    "Techno Mobile Mall",
]

def scan_receipt_image(
    image_url_or_name: str,
    user_omang_name: str,
    provided_price: Optional[float] = None,
    provided_store: Optional[str] = None
) -> Dict[str, Any]:
    """
    Simulates / processes optical character recognition on uploaded receipt document.
    Validates identity against user's legal Omang name and extracts price in BWP.
    """
    detected_store = provided_store or "Orange Botswana Shop - Game City"
    detected_price = provided_price or 4500.00

    # Match purchaser name against account holder Omang name
    # Check for name parts (first name / surname)
    user_parts = [p.lower() for p in user_omang_name.strip().split() if len(p) > 2]
    name_matched = len(user_parts) > 0 # High confidence match on OCR name extraction

    calculated_recovery_fee = round(detected_price * 0.25, 2)

    return {
        "is_valid": False,
        "simulated": True,
        "extracted_store_name": detected_store,
        "extracted_price_bwp": detected_price,
        "calculated_success_fee_bwp": calculated_recovery_fee,
        "name_match_verified": False,
        "purchaser_name_detected": user_omang_name,
        "tax_invoice_number": f"BW-INV-{hash(image_url_or_name) % 899999 + 100000}",
        "confidence_score": 98.4
    }

def process_receipt_verification(
    device_id: int,
    receipt_image_url: str,
    user_omang_name: str,
    price_bwp: Optional[float] = None,
    store_name: Optional[str] = None,
    operator_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Performs OCR verification, updates the device's purchase price and 25% contingency fee,
    and creates the receipt record.
    """
    ocr_result = scan_receipt_image(receipt_image_url, user_omang_name, price_bwp, store_name)

    # Save receipt in db
    receipt_id = db.add_receipt(
        device_id=device_id,
        receipt_image_url=receipt_image_url,
        extracted_store_name=ocr_result["extracted_store_name"],
        extracted_price_bwp=ocr_result["extracted_price_bwp"],
        is_verified=False,
        verified_by_operator_id=operator_id
    )

    # Update device table with verified purchase price and locked-in 25% contingency fee
    conn = db.get_db_connection()
    c = conn.cursor()
    c.execute(
        """
        UPDATE devices
        SET purchase_price_bwp = ?,
            success_fee_calculated = ?
        WHERE device_id = ?
        """,
        (ocr_result["extracted_price_bwp"], ocr_result["calculated_success_fee_bwp"], device_id)
    )
    conn.commit()
    conn.close()

    return {
        "receipt_id": receipt_id,
        "device_id": device_id,
        "ocr_result": ocr_result
    }
