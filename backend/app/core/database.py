"""SQLite database for product metadata.

Single-file embedded database. The .db file can be committed to git so
evaluators get a pre-seeded setup with zero configuration.

Filesystem stays responsible for: PDFs, page images, structured JSON, indexes.
Database handles: product metadata, sources, categories, ingestion status.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR

DB_PATH = DATA_DIR / "local.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Thread-local connection with WAL mode for concurrent reads."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT 'generic',
            status TEXT NOT NULL DEFAULT 'draft',
            logo_path TEXT,
            manufacturer TEXT,
            item_number TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            UNIQUE(product_id, name)
        );

        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            filename TEXT NOT NULL DEFAULT '',
            path TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL DEFAULT 'manual',
            label TEXT,
            pages INTEGER,
            created_at TEXT NOT NULL,
            UNIQUE(product_id, source_id)
        );

        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'idle',
            stage TEXT NOT NULL DEFAULT 'idle',
            progress REAL NOT NULL DEFAULT 0.0,
            message TEXT NOT NULL DEFAULT '',
            error TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quick_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            message TEXT NOT NULL
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Products CRUD
# ---------------------------------------------------------------------------

def create_product(
    product_id: str,
    name: str,
    description: str = "",
    domain: str = "generic",
    status: str = "draft",
    manufacturer: str | None = None,
    item_number: str | None = None,
    logo_path: str | None = None,
) -> dict[str, Any]:
    conn = _get_conn()
    now = _now()
    conn.execute(
        """INSERT OR IGNORE INTO products
           (id, name, description, domain, status, logo_path, manufacturer, item_number, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, name, description, domain, status, logo_path, manufacturer, item_number, now, now),
    )
    conn.commit()
    return get_product(product_id)


def get_product(product_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        return None
    product = dict(row)
    product["categories"] = get_categories(product_id)
    product["sources"] = get_sources(product_id)
    product["quick_actions"] = get_quick_actions(product_id)
    product["ingestion"] = get_latest_ingestion(product_id)
    return product


def list_products() -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute("SELECT id FROM products ORDER BY name").fetchall()
    return [get_product(row["id"]) for row in rows if get_product(row["id"]) is not None]


def update_product(product_id: str, **fields: Any) -> dict[str, Any] | None:
    if not fields:
        return get_product(product_id)
    conn = _get_conn()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [_now(), product_id]
    conn.execute(f"UPDATE products SET {sets}, updated_at = ? WHERE id = ?", values)
    conn.commit()
    return get_product(product_id)


def delete_product(product_id: str) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def set_categories(product_id: str, categories: list[str]) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM categories WHERE product_id = ?", (product_id,))
    for name in categories[:3]:
        conn.execute(
            "INSERT OR IGNORE INTO categories (product_id, name) VALUES (?, ?)",
            (product_id, name.strip().lower()),
        )
    conn.commit()


def get_categories(product_id: str) -> list[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT name FROM categories WHERE product_id = ? ORDER BY id", (product_id,)
    ).fetchall()
    return [row["name"] for row in rows]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def add_source(
    product_id: str,
    source_id: str,
    filename: str,
    path: str,
    source_type: str = "manual",
    label: str | None = None,
    pages: int | None = None,
) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO sources
           (product_id, source_id, filename, path, type, label, pages, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, source_id, filename, path, source_type, label or filename, pages, _now()),
    )
    conn.commit()


def get_sources(product_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT source_id, filename, path, type, label, pages FROM sources WHERE product_id = ? ORDER BY id",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def remove_source(product_id: str, source_id: str) -> bool:
    conn = _get_conn()
    cursor = conn.execute(
        "DELETE FROM sources WHERE product_id = ? AND source_id = ?",
        (product_id, source_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_source_count(product_id: str) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM sources WHERE product_id = ?", (product_id,)
    ).fetchone()
    return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Quick Actions
# ---------------------------------------------------------------------------

def set_quick_actions(product_id: str, actions: list[dict[str, str]]) -> None:
    conn = _get_conn()
    conn.execute("DELETE FROM quick_actions WHERE product_id = ?", (product_id,))
    for action in actions:
        conn.execute(
            "INSERT INTO quick_actions (product_id, label, message) VALUES (?, ?, ?)",
            (product_id, action["label"], action["message"]),
        )
    conn.commit()


def get_quick_actions(product_id: str) -> list[dict[str, str]]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT label, message FROM quick_actions WHERE product_id = ? ORDER BY id",
        (product_id,),
    ).fetchall()
    return [{"label": row["label"], "message": row["message"]} for row in rows]


# ---------------------------------------------------------------------------
# Ingestion Status
# ---------------------------------------------------------------------------

def save_ingestion_status(
    product_id: str,
    status: str,
    stage: str = "idle",
    progress: float = 0.0,
    message: str = "",
    error: str | None = None,
) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO ingestion_jobs
           (product_id, status, stage, progress, message, error, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (product_id, status, stage, progress, message, error, _now()),
    )
    conn.commit()


def get_latest_ingestion(product_id: str) -> dict[str, Any]:
    conn = _get_conn()
    row = conn.execute(
        """SELECT status, stage, progress, message, error
           FROM ingestion_jobs WHERE product_id = ?
           ORDER BY id DESC LIMIT 1""",
        (product_id,),
    ).fetchone()
    if row is None:
        return {"status": "idle", "stage": "idle", "progress": 0.0, "message": "", "error": None}
    return dict(row)


def update_product_status(product_id: str, status: str) -> None:
    update_product(product_id, status=status)
