# ══════════════════════════════════════════════════════════════
# MATTER STORE — v12.3
# Persistent SQLite-backed matter history.
#
# v12.3 changes:
#   - reviewer_name column: logged on every save and queryable
#   - last_accessed_at column: updated on load (retention policy)
#   - INDEX on created_at for fast retention purge queries
#   - INDEX on matter_id for fast lookup
#   - deal_context_json column (carried from v12.2)
# ══════════════════════════════════════════════════════════════
import sqlite3
import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get("MATTER_DB_PATH",
    str(Path.home() / ".contractcheck_matters.db"))

_db_initialised = False
_db_lock        = threading.Lock()

_MIGRATIONS = [
    ("doc_count",          "INTEGER DEFAULT 1"),
    ("deal_context_json",  "TEXT"),
    ("reviewer_name",      "TEXT"),        # who ran the analysis
    ("last_accessed_at",   "TEXT"),        # updated on every load
]

_SAFE_COL = re.compile(r'^[a-z_]+$')


@contextmanager
def _get_conn():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def _init_db_impl():
    with _get_conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS matters (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at        TEXT    NOT NULL,
                matter_id         TEXT,
                name              TEXT    NOT NULL,
                contract_type     TEXT,
                province          TEXT,
                client_role       TEXT,
                risk_level        TEXT,
                risk_score        INTEGER,
                verdict           TEXT,
                cost_usd          REAL,
                model             TEXT,
                analysis_json     TEXT    NOT NULL,
                char_count        INTEGER,
                doc_count         INTEGER DEFAULT 1,
                deal_context_json TEXT,
                reviewer_name     TEXT,
                last_accessed_at  TEXT
            )
        """)

        # Indexes for performance
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_matters_created_at
            ON matters(created_at)
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_matters_matter_id
            ON matters(matter_id)
        """)

        # Safe column migrations for older databases
        existing = {r[1] for r in c.execute("PRAGMA table_info(matters)")}
        for col, defn in _MIGRATIONS:
            if col not in existing:
                if not _SAFE_COL.match(col):
                    raise ValueError(f"Unsafe column name: {col!r}")
                c.execute(f'ALTER TABLE matters ADD COLUMN "{col}" {defn}')
        # Ensure indexes exist after migration too
        c.execute("CREATE INDEX IF NOT EXISTS idx_matters_created_at ON matters(created_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_matters_matter_id  ON matters(matter_id)")


def init_db():
    global _db_initialised
    if not _db_initialised:
        with _db_lock:
            if not _db_initialised:
                _init_db_impl()
                _db_initialised = True


def save_matter(name, matter_id, contract_type, province, client_role,
                risk_level, risk_score, verdict, cost_usd, model,
                analysis_json_obj, char_count, doc_count=1,
                deal_context_json_obj=None, reviewer_name=None):
    """Persist one analysis.

    reviewer_name is stored per-record so firms can query which lawyer
    reviewed each matter — required for Law Society accountability.
    analysis_json_obj should already have verbatim contract text stripped.
    """
    init_db()
    with _get_conn() as c:
        cursor = c.execute("""
            INSERT INTO matters
            (created_at, matter_id, name, contract_type, province, client_role,
             risk_level, risk_score, verdict, cost_usd, model, analysis_json,
             char_count, doc_count, deal_context_json, reviewer_name, last_accessed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            datetime.now().isoformat(),
            matter_id     or "",
            name,
            contract_type or "",
            province      or "",
            client_role   or "",
            risk_level    or "",
            risk_score    or 0,
            verdict       or "",
            cost_usd      or 0.0,
            model         or "",
            json.dumps(analysis_json_obj),
            char_count    or 0,
            doc_count,
            json.dumps(deal_context_json_obj) if deal_context_json_obj else None,
            reviewer_name or "",
            datetime.now().isoformat(),
        ))
        return cursor.lastrowid


def list_matters(limit=50):
    init_db()
    with _get_conn() as c:
        rows = c.execute("""
            SELECT id, created_at, matter_id, name, contract_type,
                   province, risk_level, risk_score, cost_usd, doc_count,
                   reviewer_name, last_accessed_at
            FROM matters ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def load_matter(row_id):
    """Load a matter and update last_accessed_at timestamp."""
    init_db()
    now = datetime.now().isoformat()
    with _get_conn() as c:
        c.execute("UPDATE matters SET last_accessed_at=? WHERE id=?", (now, row_id))
        row = c.execute("SELECT * FROM matters WHERE id=?", (row_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("analysis_json", "deal_context_json"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


def delete_matter(row_id):
    init_db()
    with _get_conn() as c:
        c.execute("DELETE FROM matters WHERE id=?", (row_id,))


def matter_count():
    init_db()
    with _get_conn() as c:
        return c.execute("SELECT COUNT(*) FROM matters").fetchone()[0]


def matters_by_reviewer(reviewer: str, limit: int = 100) -> list:
    """Return all matters for a given reviewer — supports Law Society audits."""
    init_db()
    with _get_conn() as c:
        rows = c.execute("""
            SELECT id, created_at, matter_id, name, contract_type,
                   province, risk_level, risk_score, reviewer_name
            FROM matters
            WHERE reviewer_name = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (reviewer, limit)).fetchall()
    return [dict(r) for r in rows]
