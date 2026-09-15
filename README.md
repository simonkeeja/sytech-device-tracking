# SYTECH device tracking prototype

A local FastAPI/SQLite application with an HTML/JavaScript dashboard and experimental Android and Windows clients. This is not a production recovery service.

## Current status

Implemented: account registration/login, customer ownership checks, operator/admin roles, device registration, estimated fees, demo checkout, restricted operator event feed, and downloadable demonstration reports.

Not implemented: real payment processing, receipt OCR/identity verification, real identity enrichment, cloud data recovery, remote wipe, or production device enrollment. Simulated telemetry and checkout require explicit demo mode. Receipts remain unverified. PDF exports are demonstration reports, not police affidavits. Device-client payloads include hardcoded sample values; these clients are not production ready and do not currently authenticate to the protected operator simulation endpoint.

## Windows setup

Use Python 3.12. The local `.venv` created during development is available on this machine. For a fresh checkout:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
```

`requirements.lock` pins the full tested environment; `requirements.txt` and `requirements-dev.txt` list direct dependencies.

Before the first launch, set an administrator contact and unique password (at least 12 characters). The bootstrap only creates an administrator when none exists. Do not commit credentials.

```powershell
$env:SYTECH_ADMIN_CONTACT = "your-admin-contact"
$env:SYTECH_ADMIN_PASSWORD = "replace-with-a-unique-long-password"
.\.venv\Scripts\python.exe run_server.py
```

Open http://127.0.0.1:8000/dashboard/ and sign in. The server binds to loopback only. New customer accounts can be registered through `/docs`; customers cannot promote themselves. New devices require a 6-12 digit backup PIN, stored as a password hash. Existing legacy PIN records remain compatible and should be replaced before real use.

## Optional isolated demonstration

Stop the server first. Use a separate, new database to avoid mixing sample records with existing data:

```powershell
$env:SYTECH_DB_PATH = "$PWD\demo.db"
$env:SYTECH_DEMO_MODE = "1"
.\.venv\Scripts\python.exe -m backend.database.seed
.\.venv\Scripts\python.exe run_server.py
```

Seed once per empty demo database. Seeded customer accounts have disabled passwords; sign in using the environment-bootstrapped administrator. Demo checkout transfers no money. Disable demo mode and restart to disable simulated checkout and telemetry. Existing sample records do not become verified by disabling demo mode.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
node --check dashboard/public/app.js
```

Tests create disposable databases and report directories. They never seed or modify the normal application database. Coverage includes authentication, ownership, secret redaction, invoice entitlements, simulation gates, PIN hashing, reset tokens and WebSocket access.

## Architecture

- `backend/app.py`: API and operator WebSocket feed.
- `backend/security.py`: password hashing, roles and eight-hour in-memory sessions.
- `backend/database/`: SQLite schema, queries and explicit demo seed.
- `backend/services/`: simulation helpers and demonstration report generation.
- `dashboard/public/`: same-origin dashboard and authenticated PDF download.
- `trapphon-android/`, `traplap-windows/`: experimental device clients.
- `tests/`: isolated regression suite.

## Remaining work

Production device enrollment and credentials; login/PIN rate limiting; persistent revocable sessions; database uniqueness and transaction hardening; real payment integration; receipt review workflow; broader browser coverage and real device testing. No Git repository was initialized by this change. Existing records were not migrated or deleted.

## Last completed checkpoint (11 September 2026)

Completed the desktop browser walkthrough using a disposable database in
`tmp/browser-20260911/`, separate from the normal application database:

- Customer sign-in, empty account, device registration and sign-out.
- Administrator WebSocket connection and live simulated telemetry.
- Customer checkout cancellation and successful demo dossier settlement.
- Authenticated PDF download; the downloaded file matched the generated report.
- Incorrect backup PIN rejection and successful owner reset, retaining history.
- A second customer saw no devices and received HTTP 403 for the first customer's
  device details, preview and PDF.

Fixed missing WebSocket support (pinned `wsproto`), live table refresh and column
mapping, in-page action confirmation, and stale official-report/reset wording.
Validation: 21 regression tests passed; JavaScript syntax and dependency checks
passed. Test-client dependency deprecation warnings remain.

Next: production device enrollment and per-device authentication, followed by
real device telemetry testing. Mobile/responsive coverage and production
integrations remain outside this completed desktop demo walkthrough.
