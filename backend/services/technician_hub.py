"""
SYTECH Technician Hub Tracking Engine (Version 4.0)
Detects technician-fenced clearinghouses across Gaborone:
If multiple stolen devices ping from the exact same network hardware (BSSID) or cluster
around known technician hotspots (Gaborone Station, African Mall, Main Mall),
the system flags the hub for law enforcement intervention.
"""
from typing import List, Dict, Any, Optional
from ..database import db

GABORONE_HOTSPOTS = [
    {"name": "African Mall Electronics Hub", "lat": -24.6542, "lng": 25.9085, "radius_km": 0.3},
    {"name": "Gaborone Station / Bus Rank Tech Market", "lat": -24.6580, "lng": 25.9060, "radius_km": 0.4},
    {"name": "Main Mall Tech Repair Street", "lat": -24.6570, "lng": 25.9180, "radius_km": 0.3},
    {"name": "BBS Mall / Broadhurst Tech Complex", "lat": -24.6310, "lng": 25.9320, "radius_km": 0.4}
]

def analyze_bssid_clusters() -> List[Dict[str, Any]]:
    """
    Analyzes all logged tracking telemetry to find duplicate BSSID pings across different devices.
    Flags locations where 2+ unique devices pinged the same router MAC address.
    """
    conn = db.get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT ti.nearby_wifi_macs, ti.captured_ip, ti.coarse_latitude, ti.coarse_longitude,
               ti.device_id, d.brand, d.model, d.hardware_identifier, ti.logged_at
        FROM tracking_intel ti
        JOIN devices d ON ti.device_id = d.device_id
        WHERE ti.nearby_wifi_macs IS NOT NULL AND ti.nearby_wifi_macs != ''
    """)
    rows = c.fetchall()
    conn.close()

    bssid_device_map: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        row_dict = dict(row)
        macs_raw = row_dict["nearby_wifi_macs"]
        # Can be comma-separated or json list
        mac_list = [m.strip().upper() for m in macs_raw.replace('"', '').replace('[', '').replace(']', '').split(',') if m.strip()]
        for mac in mac_list:
            if mac not in bssid_device_map:
                bssid_device_map[mac] = []
            # Check if this device is already recorded for this mac
            if not any(item["device_id"] == row_dict["device_id"] for item in bssid_device_map[mac]):
                bssid_device_map[mac].append(row_dict)

    flagged_hubs = []
    for bssid, devices in bssid_device_map.items():
        if len(devices) >= 2: # 2 or more distinct devices detected
            # Determine nearest Gaborone landmark
            first_dev = devices[0]
            lat = first_dev.get("coarse_latitude") or -24.6542
            lng = first_dev.get("coarse_longitude") or 25.9085

            location_name = "Gaborone Technician Workshop"
            for spot in GABORONE_HOTSPOTS:
                # Approximate distance calculation
                d_lat = abs(lat - spot["lat"])
                d_lng = abs(lng - spot["lng"])
                if d_lat < 0.005 and d_lng < 0.005:
                    location_name = spot["name"]
                    break

            flagged_hubs.append({
                "bssid": bssid,
                "location_zone": location_name,
                "latitude": lat,
                "longitude": lng,
                "distinct_devices_count": len(devices),
                "compromised_devices": [
                    {
                        "device_id": d["device_id"],
                        "model": f"{d['brand']} {d['model']}",
                        "imei_or_serial": d["hardware_identifier"],
                        "timestamp": d["logged_at"]
                    }
                    for d in devices
                ],
                "threat_level": "CRITICAL: High-Volume Technician Clearinghouse" if len(devices) >= 3 else "WARNING: Suspect Repair Hub",
                "recommended_action": "Coordinate with Gaborone Central Police Station CID for hardware raid."
            })

    return flagged_hubs
