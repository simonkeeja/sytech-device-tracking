"""
Tests for Official Cyber Evidence Affidavit PDF Generation (Version 4.0)
"""
import os
import pytest
from backend.services import affidavit_generator
from backend.database import db

def test_generate_police_affidavit():
    # Generate affidavit for Device 1
    pdf_path = affidavit_generator.generate_police_affidavit_pdf(device_id=1)
    assert os.path.exists(pdf_path)
    assert pdf_path.endswith(".pdf")
    # Verify non-empty file
    file_size = os.path.getsize(pdf_path)
    assert file_size > 1000 # Minimum size for complete ReportLab PDF
