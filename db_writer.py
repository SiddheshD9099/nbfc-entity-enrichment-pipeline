"""Persist enrichment results to SQLite (default) or PostgreSQL."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TABLE_NAME = "entity_enrichment"

COLUMNS = [
    "entity_name",
    "entity_type",
    "company_website",
    "company_linkedin",
    "company_address",
    "employee_size",
    "contacts",
    "source",
    "validation_status",
    "enriched_at",
]

_CREATE_SQLITE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    entity_type TEXT,
    company_website TEXT,
    company_linkedin TEXT,
    company_address TEXT,
    employee_size TEXT,
    contacts TEXT,
    source TEXT,
    validation_status TEXT,
    enriched_at TEXT NOT NULL
);
"""

_CREATE_POSTGRES = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id SERIAL PRIMARY KEY,
    entity_name TEXT NOT NULL,
    entity_type TEXT,
    company_website TEXT,
    company_linkedin TEXT,
    company_address TEXT,
    employee_size TEXT,
    contacts TEXT,
    source TEXT,
    validation_status TEXT,
    enriched_at TIMESTAMPTZ NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(_CREATE_SQLITE)
    return conn


def _connect_postgres(url: str):
    try:
        import psycopg2
    except ImportError as e:
        raise RuntimeError(
            "PostgreSQL URL set but psycopg2 is not installed. "
            "Use pip install psycopg2-binary or unset LEADLENS_DATABASE_URL."
        ) from e
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(_CREATE_POSTGRES)
    conn.commit()
    cur.close()
    return conn


def get_connection(
    database_url: str | None = None,
    sqlite_path: str | Path | None = None,
):
    url = database_url or os.environ.get("LEADLENS_DATABASE_URL")
    if url:
        if url.startswith("sqlite:"):
            # sqlite:///./leadlens.db
            path = url.replace("sqlite:///", "", 1)
            return _connect_sqlite(path)
        return _connect_postgres(url)
    return _connect_sqlite(sqlite_path or os.environ.get("LEADLENS_SQLITE_PATH", "leadlens.db"))


def _row_to_values(row: dict[str, Any]) -> tuple:
    enriched_at = row.get("enriched_at") or _now_iso()
    return (
        row.get("entity_name"),
        row.get("entity_type"),
        row.get("company_website"),
        row.get("company_linkedin"),
        row.get("company_address"),
        row.get("employee_size"),
        row.get("contacts"),
        row.get("source"),
        row.get("validation_status"),
        enriched_at,
    )


def upsert_rows(rows: list[dict], database_url: str | None = None, sqlite_path: str | Path | None = None) -> None:
    if not rows:
        return
    conn = get_connection(database_url=database_url, sqlite_path=sqlite_path)
    placeholders = ", ".join("?" if isinstance(conn, sqlite3.Connection) else "%s" for _ in COLUMNS)
    col_list = ", ".join(COLUMNS)
    sql = f"INSERT INTO {TABLE_NAME} ({col_list}) VALUES ({placeholders})"
    try:
        cur = conn.cursor()
        for row in rows:
            cur.execute(sql, _row_to_values(row))
        conn.commit()
    finally:
        conn.close()
