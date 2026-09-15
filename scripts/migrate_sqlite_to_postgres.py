"""One-time migration of the existing SYTECH SQLite data to Supabase PostgreSQL.

Usage (PowerShell):
  $env:DATABASE_URL='postgresql://...'
  python scripts/migrate_sqlite_to_postgres.py

The script refuses to overwrite non-empty destination tables.
"""
import os
import sqlite3
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
SQLITE_PATH = Path(os.getenv("SYTECH_DB_PATH", ROOT / "backend" / "database" / "sytech.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

TABLES = [
    ("users", "user_id"),
    ("devices", "device_id"),
    ("receipts", "receipt_id"),
    ("tracking_intel", "intel_id"),
    ("face_search_results", "match_id"),
    ("false_alarm_logs", "log_id"),
    ("financial_invoices", "invoice_id"),
    ("checkout_requests", None),
]


def main():
    if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        raise SystemExit("Set DATABASE_URL to the Supabase Postgres connection string first.")
    if not SQLITE_PATH.exists():
        raise SystemExit(f"SQLite database not found: {SQLITE_PATH}")

    src = sqlite3.connect(SQLITE_PATH)
    src.row_factory = sqlite3.Row
    dst = psycopg.connect(DATABASE_URL, row_factory=dict_row)

    try:
        for table, _ in TABLES:
            count = dst.execute(f'SELECT COUNT(*) AS n FROM "{table}"').fetchone()["n"]
            if count:
                raise SystemExit(f"Destination table {table} is not empty ({count} rows). Migration aborted before copying data.")

        with dst.transaction():
            for table, pk in TABLES:
                rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
                if not rows:
                    print(f"{table}: 0 rows")
                    continue
                columns = list(rows[0].keys())
                quoted = ", ".join(f'"{c}"' for c in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                sql = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'
                for row in rows:
                    values = [bool(row[c]) if c in {"is_registration_paid", "local_bootloader_secured", "is_verified", "is_settled"} and row[c] is not None else row[c] for c in columns]
                    dst.execute(sql, values)
                print(f"{table}: {len(rows)} rows")

            for table, pk in TABLES:
                if pk:
                    seq = dst.execute("SELECT pg_get_serial_sequence(%s, %s) AS seq", (table, pk)).fetchone()["seq"]
                    if seq:
                        max_id = dst.execute(f'SELECT COALESCE(MAX("{pk}"), 0) AS m FROM "{table}"').fetchone()["m"]
                        if max_id:
                            dst.execute("SELECT setval(%s, %s, true)", (seq, max_id))
        print("Migration complete.")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
