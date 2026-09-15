# SYTECH TrapPhon - Google Play Store Publication & Policy Readiness Guide

This guide provides the complete compliance documentation, declarations, and copy required to publish **TrapPhon (SYTECH Device Protection)** to the Google Play Console in compliance with Google Play Developer Program Policies.

---

## 1. Google Play Policy Compliance Overview

### A. Device Administration Policy (`BIND_DEVICE_ADMIN`)
Google Play allows apps to request Device Administrator permissions **only** for specific use cases including Anti-Theft, Enterprise Mobility Management (EMM), and Device Security.
- **TrapPhon Declaration:** TrapPhon implements the `watch-login` and `force-lock` policies to detect when an unauthorized handler attempts repeated unauthorized access ($\ge 3$ failed PIN/password attempts) and triggers an offline security lockdown to safeguard personal data.
- **Prominent In-App Disclosure:** TrapPhon displays a prominent disclosure dialog explaining why the permission is required *before* presenting the system `ACTION_ADD_DEVICE_ADMIN` activation screen.

### B. Background Location & Foreground Service
- **Foreground Service Type:** `specialUse` (with subtype `AntiTheftIntelRecovery`)
- **Justification:** Continuous monitoring of baseband hardware states (SIM card swap detection) and network connectivity changes to safeguard stolen hardware.

### C. SMS & Telephony Declarations (`READ_PHONE_STATE`, `SEND_SMS`)
- **Core Functionality:** Stolen device tracking across Botswana cellular networks (Orange Botswana, Mascom Wireless, BTC Mobile) when mobile data connectivity is physically disabled by a suspect.
- **Alternative:** Telemetry is primarily sent via encrypted HTTPS when Wi-Fi/cellular data is active; SMS is utilized strictly as an offline baseband fallback.

---

## 2. Google Play Console Data Safety Form Declarations

| Category | Data Type | Purpose | Shared / Ephemeral | Encrypted in Transit? |
| :--- | :--- | :--- | :--- | :--- |
| **Location** | Coarse & Approximate Location | Anti-theft recovery evidence for police reporting | Shared only upon user consent with Botswana Police | Yes (HTTPS) |
| **Personal Info** | Full Legal Name (Omang), Phone Number | Account identity & proof of ownership | Not shared with 3rd parties | Yes (HTTPS) |
| **Device IDs** | IMEI, SIM IMSI, Carrier Name | Hardware binding & SIM swap detection | Retained for recovery dossier | Yes (HTTPS) |

---

## 3. Play Store Listing Metadata

### App Title
`SYTECH: Anti-Theft & Device Guard`

### Short Description (80 chars max)
`Active Honeypot protection, SIM swap detection & anti-theft evidence recovery.`

### Full Description (4000 chars max)
```
SYTECH DEVICE TRACKING alters the power dynamic of smartphone security by shifting from passive tracking to Active Honey-Pot Trapping.

Traditional tracking apps fail the moment a thief cuts off internet connectivity, removes your SIM card, or brings your phone to a street technician. SYTECH protects your digital life before hardware can be wiped.

KEY FEATURES:
🛡️ Offline Honeypot Lockdown: If an unauthorized user logs 3 consecutive failed PIN attempts, the system enters an offline security lockdown to protect personal photos, contacts, and banking credentials.
📡 SIM Interception: Detects when an unauthorized SIM is inserted (Orange, Mascom, BTC) and silently transmits recovery telemetry to our secure cloud dashboard.
📑 Official Police Evidence Affidavit: Generates an un-blurred forensic dossier citing Botswana's Cybercrime and Computer Related Crimes Act (Act No. 18 of 2018) for immediate handover to Botswana Police Service (BPS) officers.
⚡ 5-Tap Owner Emergency Exit: Accidental lock? Simply tap the company logo 5 times to enter your private 4-digit Master Backup PIN.

OPERATIONS & REGISTRATION:
Engineered for Botswana. Zero upfront barrier to entry with deferred registration fees. Store purchase receipts verified via automated OCR.

PROMINENT DISCLOSURE:
This application utilizes the Device Administrator (BIND_DEVICE_ADMIN) permission to detect failed screen lock attempts and safeguard personal data during unauthorized access attempts.
```

---

## 4. Privacy Policy (Republic of Botswana & Play Store Compliant)

**Effective Date:** 7 September 2026  
**Entity:** SYTECH Intelligence Systems Botswana (Plot 54368, iTowers, CBD, Gaborone)  
**Governing Law:** Data Protection Act (Act No. 32 of 2018) & Cybercrime and Computer Related Crimes Act (Act No. 18 of 2018)

1. **Information Collected:** We collect your Omang-verified legal name, contact telephone numbers, device hardware identifiers (IMEI, Serial Number), store purchase receipt images, and network telemetry (carrier name, SIM IMSI, approximate geolocation) strictly to deliver anti-theft protection.
2. **Data Retention & Encryption:** All data transmitted between TrapPhon and the SYTECH Cloud is encrypted in transit using TLS 1.3. Evidence is retained solely until the resolution or cancellation of a recovery case.
3. **Sharing with Law Enforcement:** Cyber evidence dossiers are compiled exclusively for the registered owner and are designed for direct presentation to the Botswana Police Service (BPS) and Criminal Investigation Department (CID).
4. **Owner Control:** You retain the right to deactivate Device Administrator permissions, modify your Master Backup PIN, or delete your account data at any time via the settings menu.
