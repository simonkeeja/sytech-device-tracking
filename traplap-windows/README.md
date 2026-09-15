# SYTECH TrapLap - Windows Laptop Tracking & Anti-Format Module (Version 4.0)

## Overview
TrapLap hardens laptops against independent tech technicians (e.g., around Gaborone Station, African Mall, or Main Mall) who attempt to format or bypass Windows login credentials.

### Key Anti-Format Protections:
1. **Boot Configuration Spoofing:** Alters Windows Boot Configuration Data (BCD) to skip standard password screens and enter a fake guest profile, delaying clean OS wipe attempts.
2. **Offline Hardware Triggers:** Logs failed login attempts ($\ge 3$) or hardware interrupt keys (F12/F2/Del).
3. **Captive Network Trapping:** Renders a full-screen lockdown overlay. The moment a technician connects to local Wi-Fi, the daemon scans surrounding router MACs (`netsh wlan show networks mode=bssid`) and broadcasts them to the SYTECH Cloud.
4. **Front Webcam Silent Flash:** Silently captures the user's face upon mouse movement for OSINT reverse-image indexing.
5. **The Owner's Exit:** 5 rapid clicks on the SYTECH shield logo opens the Master Backup PIN verification dialog (Default: `7924`).

## Running the Daemon
```bash
py -3 -m traplap_windows.traplap_daemon
```
