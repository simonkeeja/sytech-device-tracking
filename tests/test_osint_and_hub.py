"""
Tests for OSINT intelligence pipeline and Technician Hub clustering in Gaborone (Version 4.0)
"""
import pytest
from backend.services import osint_pipeline, technician_hub
from backend.database import db

def test_financial_kyc_lookup():
    # Known registry test
    kyc_orange = osint_pipeline.lookup_financial_kyc("+26771234567")
    assert kyc_orange["name"] == "Thatayaone Motlhanka"
    assert kyc_orange["carrier"] == "Orange Botswana"
    assert kyc_orange["wallet"] == "Orange Money"

    # Secondary number test
    kyc_mascom = osint_pipeline.lookup_financial_kyc("+26772345678")
    assert kyc_mascom["name"] == "Kabo Kgosietsile"
    assert kyc_mascom["carrier"] == "Mascom Wireless"
    assert kyc_mascom["wallet"] == "MyZaka"

def test_reverse_face_indexing():
    matches = osint_pipeline.run_reverse_face_indexing("test_photo_url.jpg", "Thatayaone Motlhanka")
    assert len(matches) >= 2
    assert matches[0]["confidence_score"] > 80.0
    assert matches[0]["resolved_name"] == "Thatayaone Motlhanka"

def test_technician_hub_clustering():
    # In seed.py, Device 1 and Device 3 both logged BSSID: A4:2B:B0:19:C2:5E
    hubs = technician_hub.analyze_bssid_clusters()
    assert len(hubs) >= 1
    station_hub = next((h for h in hubs if "A4:2B:B0:19:C2:5E" in h["bssid"]), None)
    assert station_hub is not None
    assert station_hub["distinct_devices_count"] >= 2
    assert any(zone in station_hub["location_zone"] for zone in ["African Mall", "Gaborone Station", "Main Mall", "Technician"])
    assert "CRITICAL" in station_hub["threat_level"] or "WARNING" in station_hub["threat_level"]
