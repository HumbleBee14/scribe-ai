"""SQLite database for product metadata.

Single-file embedded database. The .db file can be committed to git so
evaluators get a pre-seeded setup with zero configuration.

Filesystem stays responsible for: PDFs, page images, structured JSON, indexes.
Database handles: product metadata, sources, categories, ingestion status.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import DATA_DIR

logger = logging.getLogger(__name__)

DB_PATH = DATA_DIR / "local.db"

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Thread-local connection with WAL mode and sqlite-vec loaded."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # Load sqlite-vec extension for native vector search
        try:
            import sqlite_vec
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except ImportError:
            pass  # sqlite-vec not installed, vector search unavailable
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
            custom_prompt TEXT NOT NULL DEFAULT '',
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
            processing_status TEXT NOT NULL DEFAULT 'pending',
            pages_rendered INTEGER DEFAULT 0,
            chunks_extracted INTEGER DEFAULT 0,
            processing_error TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(product_id, source_id)
        );

        CREATE TABLE IF NOT EXISTS quick_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS page_analysis (
            product_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            filename TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            detailed_text TEXT NOT NULL DEFAULT '',
            keywords TEXT NOT NULL DEFAULT '',
            is_toc BOOLEAN DEFAULT FALSE,
            processing_status TEXT NOT NULL DEFAULT 'pending',
            PRIMARY KEY (product_id, source_id, page),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS page_embeddings (
            product_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            page INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            PRIMARY KEY (product_id, source_id, page),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS toc_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            start_page INTEGER NOT NULL,
            end_page INTEGER,
            level INTEGER DEFAULT 1,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
    """)

    # FTS5 virtual table for full-text search across page content
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(
                summary, detailed_text, keywords,
                content=page_analysis,
                content_rowid=rowid
            )
        """)
    except Exception:
        pass  # FTS5 table already exists

    # sqlite-vec virtual table for native vector similarity search
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS page_vec USING vec0(
                embedding float[384]
            )
        """)
    except Exception:
        pass  # sqlite-vec not available or table exists

    conn.commit()

    # Migrations: add columns that may not exist in older databases
    _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns to existing tables if missing. Safe to run repeatedly."""
    migrations = [
        ("sources", "processing_status", "TEXT DEFAULT 'pending'"),
        ("sources", "pages_rendered", "INTEGER DEFAULT 0"),
        ("sources", "chunks_extracted", "INTEGER DEFAULT 0"),
        ("sources", "processing_error", "TEXT"),
        ("page_analysis", "filename", "TEXT DEFAULT ''"),
        ("products", "custom_prompt", "TEXT DEFAULT ''"),
    ]
    for table, column, coltype in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        except sqlite3.OperationalError:
            pass  # column already exists
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
    # Derive ingestion status from source processing statuses
    sources = product["sources"]
    if not sources:
        product["ingestion"] = {"status": product["status"], "message": ""}
    elif all(s.get("processing_status") == "done" for s in sources):
        product["ingestion"] = {"status": "ready", "message": "All documents processed."}
    elif any(s.get("processing_status") == "pending" for s in sources):
        product["ingestion"] = {"status": "processing", "message": "Processing documents..."}
    else:
        product["ingestion"] = {"status": product["status"], "message": ""}
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
           (product_id, source_id, filename, path, type, label, pages, processing_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
        (product_id, source_id, filename, path, source_type, label or filename, pages, _now()),
    )
    conn.commit()


def get_sources(product_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT source_id, filename, path, type, label, pages,
                  processing_status, pages_rendered, chunks_extracted, processing_error
           FROM sources WHERE product_id = ? ORDER BY id""",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def update_source_processing(
    product_id: str,
    source_id: str,
    status: str,
    pages_rendered: int = 0,
    chunks_extracted: int = 0,
    error: str | None = None,
) -> None:
    conn = _get_conn()
    conn.execute(
        """UPDATE sources SET processing_status = ?, pages_rendered = ?,
           chunks_extracted = ?, processing_error = ?
           WHERE product_id = ? AND source_id = ?""",
        (status, pages_rendered, chunks_extracted, error, product_id, source_id),
    )
    conn.commit()


def get_pending_sources(product_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT source_id, filename, path, type, label, pages
           FROM sources WHERE product_id = ? AND processing_status = 'pending'
           ORDER BY id""",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def all_sources_processed(product_id: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM sources WHERE product_id = ? AND processing_status != 'done'",
        (product_id,),
    ).fetchone()
    return row["c"] == 0


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




def update_product_status(product_id: str, status: str) -> None:
    update_product(product_id, status=status)


# ---------------------------------------------------------------------------
# Page Analysis (OCR results from Claude Vision)
# ---------------------------------------------------------------------------

def register_rendered_page(
    product_id: str,
    source_id: str,
    page: int,
    filename: str,
) -> None:
    """Register a rendered page in DB with pending status (Stage 1)."""
    conn = _get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO page_analysis
           (product_id, source_id, page, filename, processing_status)
           VALUES (?, ?, ?, ?, 'pending')""",
        (product_id, source_id, page, filename),
    )
    conn.commit()


def update_source_pages(product_id: str, source_id: str, total_pages: int) -> None:
    """Update the page count on a source after rendering."""
    conn = _get_conn()
    conn.execute(
        "UPDATE sources SET pages = ?, pages_rendered = ? WHERE product_id = ? AND source_id = ?",
        (total_pages, total_pages, product_id, source_id),
    )
    conn.commit()


def update_page_status(product_id: str, source_id: str, page: int, status: str) -> None:
    """Update processing status for a single page."""
    conn = _get_conn()
    conn.execute(
        "UPDATE page_analysis SET processing_status = ? "
        "WHERE product_id = ? AND source_id = ? AND page = ?",
        (status, product_id, source_id, page),
    )
    conn.commit()


def get_rendered_pages(product_id: str, source_id: str) -> list[dict[str, Any]]:
    """Get all rendered pages for a source with their processing status."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT page, filename, processing_status FROM page_analysis "
        "WHERE product_id = ? AND source_id = ? ORDER BY page",
        (product_id, source_id),
    ).fetchall()
    return [dict(row) for row in rows]


def upsert_page_analysis(
    product_id: str,
    source_id: str,
    page: int,
    summary: str,
    detailed_text: str,
    keywords: str,
    is_toc: bool = False,
) -> None:
    """Update a page with OCR analysis results (Stage 2). Preserves filename."""
    conn = _get_conn()
    # Get existing filename
    existing = conn.execute(
        "SELECT filename FROM page_analysis WHERE product_id = ? AND source_id = ? AND page = ?",
        (product_id, source_id, page),
    ).fetchone()
    filename = existing["filename"] if existing else f"page_{page:02d}.png"

    conn.execute(
        """INSERT OR REPLACE INTO page_analysis
           (product_id, source_id, page, filename, summary, detailed_text, keywords, is_toc, processing_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'done')""",
        (product_id, source_id, page, filename, summary, detailed_text, keywords, is_toc),
    )
    # Sync FTS5 index
    try:
        conn.execute(
            "INSERT OR REPLACE INTO page_fts(rowid, summary, detailed_text, keywords) "
            "SELECT rowid, summary, detailed_text, keywords FROM page_analysis "
            "WHERE product_id = ? AND source_id = ? AND page = ?",
            (product_id, source_id, page),
        )
    except Exception:
        pass  # FTS5 sync best-effort
    conn.commit()


def get_page_analysis(product_id: str, source_id: str, page: int) -> dict[str, Any] | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM page_analysis WHERE product_id = ? AND source_id = ? AND page = ?",
        (product_id, source_id, page),
    ).fetchone()
    return dict(row) if row else None


def get_all_page_summaries(product_id: str) -> list[dict[str, Any]]:
    """Get all page summaries for a product (for the document map)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT source_id, page, summary, is_toc FROM page_analysis "
        "WHERE product_id = ? ORDER BY source_id, page",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_toc_pages(product_id: str) -> list[dict[str, Any]]:
    """Get all TOC page content for a product."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT source_id, page, detailed_text FROM page_analysis "
        "WHERE product_id = ? AND is_toc = TRUE ORDER BY source_id, page",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_page_detailed_text(product_id: str, source_id: str, pages: list[int]) -> list[dict[str, Any]]:
    """Get detailed text for specific pages (when agent requests more context)."""
    conn = _get_conn()
    placeholders = ",".join("?" for _ in pages)
    rows = conn.execute(
        f"SELECT source_id, page, detailed_text, keywords FROM page_analysis "
        f"WHERE product_id = ? AND source_id = ? AND page IN ({placeholders}) "
        f"ORDER BY page",
        (product_id, source_id, *pages),
    ).fetchall()
    return [dict(row) for row in rows]


def search_pages_fts(product_id: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Full-text search across all page content for a product.

    Uses weighted BM25 to rank results — column order in page_fts is
    (summary, detailed_text, keywords), so weights below match that order:
      keywords column      weight=5.0  (curated, high-signal)
      summary column       weight=3.0  (short description, medium-signal)
      detailed_text column weight=1.0  (large blob, low-signal per match)

    Multi-word matches naturally outscore single-word matches because BM25 sums
    per-term scores. Stop words ("the", "is", "what") appear on nearly every
    page so their IDF approaches 0 — BM25 downweights them automatically.
    No explicit stop-word list needed.
    """
    conn = _get_conn()
    # Sanitize and convert to OR-separated tokens
    # Remove FTS5 special characters that break queries
    clean = re.sub(r'["\'\(\)\*\+\-\:\;\!\?\.\,\[\]\{\}]', ' ', query)
    tokens = [t.strip() for t in clean.split() if t.strip() and len(t.strip()) > 1]
    if not tokens:
        return []
    fts_query = " OR ".join(tokens)
    try:
        rows = conn.execute(
            """SELECT pa.source_id, pa.page, pa.summary, pa.keywords,
                      bm25(page_fts, 3.0, 1.0, 5.0) AS fts_rank
               FROM page_fts
               JOIN page_analysis pa ON page_fts.rowid = pa.rowid
               WHERE page_fts MATCH ? AND pa.product_id = ?
               ORDER BY bm25(page_fts, 3.0, 1.0, 5.0)
               LIMIT ?""",
            (fts_query, product_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("FTS5 search failed: %s", exc)
        return []


def delete_page_analysis_for_source(product_id: str, source_id: str) -> None:
    """Remove all page analysis for a source (when document is deleted)."""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM page_analysis WHERE product_id = ? AND source_id = ?",
        (product_id, source_id),
    )
    conn.execute(
        "DELETE FROM page_embeddings WHERE product_id = ? AND source_id = ?",
        (product_id, source_id),
    )
    conn.commit()


def get_page_processing_progress(product_id: str, source_id: str) -> dict[str, int]:
    """Get page-level processing progress for a source."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT processing_status, COUNT(*) as c FROM page_analysis "
        "WHERE product_id = ? AND source_id = ? GROUP BY processing_status",
        (product_id, source_id),
    ).fetchall()
    result = {"pending": 0, "ocr": 0, "done": 0, "failed": 0, "total": 0}
    for row in rows:
        status = row["processing_status"]
        count = row["c"]
        if status in result:
            result[status] = count
        result["total"] += count
    return result


# ---------------------------------------------------------------------------
# Page Embeddings
# ---------------------------------------------------------------------------

def upsert_page_embedding(product_id: str, source_id: str, page: int, embedding: bytes) -> None:
    """Store embedding in both metadata table and vec0 search table."""
    conn = _get_conn()
    # Store in metadata table (has product_id, source_id for filtering)
    conn.execute(
        """INSERT OR REPLACE INTO page_embeddings
           (product_id, source_id, page, embedding)
           VALUES (?, ?, ?, ?)""",
        (product_id, source_id, page, embedding),
    )
    # Get the rowid for the vec0 table
    row = conn.execute(
        "SELECT rowid FROM page_embeddings WHERE product_id = ? AND source_id = ? AND page = ?",
        (product_id, source_id, page),
    ).fetchone()
    if row:
        # Sync to vec0 table for native vector search
        try:
            conn.execute(
                "INSERT OR REPLACE INTO page_vec(rowid, embedding) VALUES (?, ?)",
                (row["rowid"], embedding),
            )
        except Exception:
            pass  # sqlite-vec not available
    conn.commit()


def search_by_embedding(product_id: str, query_embedding: bytes, limit: int = 10) -> list[dict[str, Any]]:
    """Find most similar pages using native sqlite-vec vector search.

    Two-step: vec search first (fast), then enrich with metadata.
    """
    conn = _get_conn()
    try:
        # Step 1: Vector search (no JOINs - sqlite-vec works best alone)
        vec_rows = conn.execute(
            "SELECT rowid, distance FROM page_vec "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (query_embedding, limit * 3),  # fetch extra, filter by product after
        ).fetchall()

        if not vec_rows:
            return []

        # Step 2: Enrich with metadata and filter by product_id
        results = []
        for vr in vec_rows:
            pe = conn.execute(
                "SELECT product_id, source_id, page FROM page_embeddings WHERE rowid = ?",
                (vr["rowid"],),
            ).fetchone()
            if not pe or pe["product_id"] != product_id:
                continue

            pa = conn.execute(
                "SELECT summary, keywords FROM page_analysis "
                "WHERE product_id = ? AND source_id = ? AND page = ?",
                (pe["product_id"], pe["source_id"], pe["page"]),
            ).fetchone()

            results.append({
                "source_id": pe["source_id"],
                "page": pe["page"],
                "distance": vr["distance"],
                "summary": pa["summary"] if pa else "",
                "keywords": pa["keywords"] if pa else "",
            })
            if len(results) >= limit:
                break

        return results
    except Exception as exc:
        logger.warning("Vector search failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# TOC Entries
# ---------------------------------------------------------------------------

def upsert_toc_entry(
    product_id: str, source_id: str,
    title: str, start_page: int, end_page: int | None = None, level: int = 1,
) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO toc_entries
           (product_id, source_id, title, start_page, end_page, level)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (product_id, source_id, title, start_page, end_page, level),
    )
    conn.commit()


def get_toc(product_id: str) -> list[dict[str, Any]]:
    """Get all TOC entries for a product."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT source_id, title, start_page, end_page, level FROM toc_entries "
        "WHERE product_id = ? ORDER BY source_id, start_page",
        (product_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def delete_toc_for_source(product_id: str, source_id: str) -> None:
    conn = _get_conn()
    conn.execute(
        "DELETE FROM toc_entries WHERE product_id = ? AND source_id = ?",
        (product_id, source_id),
    )
    conn.commit()
