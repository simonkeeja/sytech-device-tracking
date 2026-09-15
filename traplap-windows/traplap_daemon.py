"""
TrapLap - Windows Laptop Tracking Daemon (Version 4.0)
Background daemon running as a Windows Service or background process.
Integrates:
- Hardware interrupt & failed login detection
- BSSID Wi-Fi harvester
- Front webcam silent trigger
- Central telemetry ingress to SYTECH Cloud
"""
import os
import json
import time
import urllib.request
from typing import Dict, Any

from .wifi_bssid_harvester import scan_surrounding_bssids, get_network_ip_metadata
from .captive_lockout_ui import CaptiveLockoutOverlay

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {
        "device_id": 2, # Laptop ID
        "server_url": "http://localhost:8000/api/telemetry/ingress",
        "max_failed_logins": 3,
        "master_backup_pin": "7924"
    }

def transmit_telemetry(trigger_type: str = "wifi_captive_connect"):
    config = load_config()
    bssids = scan_surrounding_bssids()
    meta = get_network_ip_metadata()

    payload = {
        "device_id": config["device_id"],
        "trigger_type": trigger_type,
        "captured_ip": meta["ip"],
        "captured_network_operator": meta["isp"],
        "nearby_wifi_macs": ",".join(bssids),
        "suspect_photo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=400&fit=crop&q=80",
        "coarse_latitude": -24.6542,
        "coarse_longitude": 25.9085
    }

    try:
        req = urllib.request.Request(
            config["server_url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode())
            print(f"[TrapLap Daemon] Telemetry successfully transmitted. Status: {res_data.get('status')}")
            return res_data
    except Exception as e:
        print(f"[TrapLap Daemon] Failed to transmit telemetry to cloud: {e}")
        return None

def run_honeypot_lockout():
    """
    Launches the captive lockout screen when trigger condition is reached.
    """
    print("[TrapLap Daemon] Trigger threshold reached. Launching Captive Lockout Overlay...")
    
    def on_wifi():
        print("[TrapLap Daemon] Wi-Fi connection detected! Harvesting surrounding router BSSIDs...")
        transmit_telemetry("wifi_captive_connect")

    def on_exit():
        print("[TrapLap Daemon] Master Backup PIN entered. Restoring standard Windows shell.")

    overlay = CaptiveLockoutOverlay(on_wifi_connect=on_wifi, on_master_exit=on_exit)
    overlay.start()

if __name__ == "__main__":
    print("[TrapLap Daemon v4.0] Monitoring Windows hardware states...")
    # Trigger demonstration
    run_honeypot_lockout()
