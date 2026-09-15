"""
SYTECH Interactive Device Simulator (Version 4.0)
Allows running a standalone CLI or Web simulation of TrapPhon and TrapLap events.
"""
import sys
import time
import requests

API_URL = "http://localhost:8000"

def simulate_trapphon_attack(device_id: int = 1):
    print(f"\n--- SIMULATING TRAPPHON ATTACK ON DEVICE #{device_id} ---")
    print("[1/3] Thief enters 3 incorrect unlock patterns on smartphone...")
    res = requests.post(f"{API_URL}/api/telemetry/ingress", json={
        "device_id": device_id,
        "trigger_type": "failed_login",
        "local_failed_attempts": 3
    })
    print("      Phone enters Fake Factory Reset / Security Lockdown screen.")
    time.sleep(1)

    print("[2/3] Thief slides in new Orange Botswana SIM card...")
    res = requests.post(f"{API_URL}/api/telemetry/ingress", json={
        "device_id": device_id,
        "trigger_type": "sim_swap",
        "new_sim_number_imsi": "652028912384910",
        "new_phone_number": "+26771234567",
        "captured_network_operator": "Orange Botswana"
    })
    data = res.json()
    enrich = data.get("enrichment", {})
    print(f"      Baseband Radio awakens. Telemetry harvested!")
    print(f"      OSINT KYC Name Extracted: {enrich.get('suspect_name')} ({enrich.get('wallet')})")
    print(f"      Face Matches Found: {enrich.get('face_matches_count')}")
    print("[3/3] Device status advanced to 'ready'. Blurred Preview active on Client Portal.")

def simulate_traplap_attack(device_id: int = 2):
    print(f"\n--- SIMULATING TRAPLAP ATTACK ON LAPTOP #{device_id} ---")
    print("[1/3] Technician attempts F12 Boot Menu interrupt...")
    print("      Laptop freezes desktop and launches Captive Portal Network Lockout.")
    time.sleep(1)

    print("[2/3] Technician connects to Wi-Fi to authenticate operating system...")
    res = requests.post(f"{API_URL}/api/telemetry/ingress", json={
        "device_id": device_id,
        "trigger_type": "wifi_captive_connect",
        "nearby_wifi_macs": "A4:2B:B0:19:C2:5E,88:DE:A9:31:8B:20",
        "captured_ip": "168.167.12.84",
        "captured_network_operator": "Botswana Telecommunications (BTC Fiber)"
    })
    print(f"      Router BSSIDs harvested. Technician Hub clustering updated.")
    print("[3/3] Front webcam silently flashed. Face vector sent to reverse image indexer.")

if __name__ == "__main__":
    print("SYTECH Interactive Hardware Simulator (v4.0)")
    print("1. Simulate TrapPhon (Mobile Honeypot + SIM Interception)")
    print("2. Simulate TrapLap (Laptop Captive Portal + BSSID Harvest)")
    choice = input("Select option (1 or 2): ").strip()
    if choice == "2":
        simulate_traplap_attack()
    else:
        simulate_trapphon_attack()
