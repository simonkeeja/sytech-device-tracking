"""Generate a demonstration report, never a verified police affidavit."""
import os
from uuid import uuid4
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from ..database import db

PDF_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated_affidavits")

def generate_police_affidavit_pdf(device_id: int, invoice_id=None) -> str:
    device = db.get_device(device_id)
    if not device:
        raise ValueError("Device not found")
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
    path = os.path.join(PDF_OUTPUT_DIR, f"SYTECH_DEMO_REPORT_{device_id}_{uuid4().hex}.pdf")
    styles = getSampleStyleSheet()
    paragraphs = [
        Paragraph("SYTECH demonstration report", styles["Title"]),
        Paragraph("SIMULATED DATA - NOT VERIFIED EVIDENCE", styles["Heading2"]),
        Paragraph("This prototype does not verify identities, receipts or payments. This document is not a police affidavit and must not be submitted as evidence or used to identify or accuse anyone.", styles["BodyText"]),
        Spacer(1, 16),
        Paragraph("Registered device", styles["Heading2"]),
        Paragraph(escape(f"Device #{device_id}: {device['brand']} {device['model']}"), styles["BodyText"]),
        Paragraph("Device details were supplied by the account holder and have not been independently verified.", styles["BodyText"]),
        Spacer(1, 16),
        Paragraph("Integration status", styles["Heading2"]),
        Paragraph("Receipt OCR, identity enrichment and payment processing are demonstration placeholders. No verified identity, payment confirmation, recovery or wipe is certified by this report.", styles["BodyText"]),
    ]
    SimpleDocTemplate(path, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42).build(paragraphs)
    return path
