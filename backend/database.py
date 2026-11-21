import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / os.environ.get("DATABASE_PATH", "duetrack.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def new_id() -> str:
    return str(uuid.uuid4())

def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def init_db():
    conn = get_connection()
    try:
        with conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
              id                  TEXT PRIMARY KEY,
              name                TEXT NOT NULL,
              username            TEXT NOT NULL UNIQUE,
              phone               TEXT NOT NULL,
              password            TEXT NOT NULL,
              encrypted_password  TEXT NOT NULL,
              role                TEXT NOT NULL CHECK (role IN ('DEALER','EMPLOYEE')),
              status              TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','INACTIVE')),
              created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );

            CREATE TABLE IF NOT EXISTS clients (
              id          TEXT PRIMARY KEY,
              name        TEXT NOT NULL,
              phone       TEXT NOT NULL,
              address     TEXT NOT NULL,
              notes       TEXT,
              created_by  TEXT REFERENCES users(id) ON DELETE SET NULL,
              created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );

            CREATE TABLE IF NOT EXISTS collections (
              id                    TEXT PRIMARY KEY,
              client_id             TEXT REFERENCES clients(id) ON DELETE SET NULL,
              assigned_employee_id  TEXT REFERENCES users(id) ON DELETE SET NULL,
              total_amount          REAL NOT NULL CHECK (total_amount >= 1),
              received_amount       REAL NOT NULL DEFAULT 0 CHECK (received_amount >= 0),
              remaining_amount      REAL NOT NULL CHECK (remaining_amount >= 0),
              status                TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PARTIALLY_COLLECTED','COMPLETED')),
              collection_date       TEXT NOT NULL,
              due_date              TEXT NOT NULL,
              notes                 TEXT,
              created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
              updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_collections_status ON collections(status);
            CREATE INDEX IF NOT EXISTS idx_collections_assigned_employee_id ON collections(assigned_employee_id);
            CREATE INDEX IF NOT EXISTS idx_collections_client_id ON collections(client_id);

            CREATE TABLE IF NOT EXISTS payments (
              id             TEXT PRIMARY KEY,
              collection_id  TEXT REFERENCES collections(id) ON DELETE SET NULL,
              client_id      TEXT REFERENCES clients(id) ON DELETE SET NULL,
              employee_id    TEXT REFERENCES users(id) ON DELETE SET NULL,
              client_name    TEXT NOT NULL,
              client_phone   TEXT NOT NULL,
              employee_name  TEXT NOT NULL,
              amount         REAL NOT NULL CHECK (amount >= 1),
              payment_method TEXT NOT NULL CHECK (payment_method IN ('CASH','BANK_TRANSFER','UPI','OTHER')),
              remarks        TEXT,
              payment_date   TEXT NOT NULL,
              created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
              verified       INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1))
            );
            CREATE INDEX IF NOT EXISTS idx_payments_collection_id_created_at ON payments(collection_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_payments_employee_id ON payments(employee_id);
            CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date);
            CREATE INDEX IF NOT EXISTS idx_payments_verified ON payments(verified);
            """)
    finally:
        conn.close()
