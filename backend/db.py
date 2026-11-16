"""
backend/db.py - Unified Database Adapter Layer (SQLite & PostgreSQL Compatible)

Provides a clean database interface that:
1. Seamlessly connects to the existing SQLite `leads.db` file by default, preserving
   all existing 27 leads, indexes, and schema.
2. Supports PostgreSQL when DATABASE_URL is set (e.g. postgresql://user:pass@host/db),
   auto-initializing the identical schema and indexes.
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import sqlite3
import json
import contextlib
import datetime
import pandas as pd
from backend.config import settings

# Base directory for resolving relative paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE_DEFAULT_PATH = os.path.join(BASE_DIR, "leads.db")

SAFE_ORDER_BY: Dict[str, str] = {
    "id_asc": "id ASC",
    "id_desc": "id DESC",
    "score_desc": "lead_score DESC, id ASC",
    "score_asc": "lead_score ASC, id ASC",
}


def is_postgres() -> bool:
    url = (settings.DATABASE_URL or "").lower()
    return url.startswith("postgresql://") or url.startswith("postgres://")


@contextlib.contextmanager
def get_connection():
    """Yields a database connection object."""
    if is_postgres():
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(settings.DATABASE_URL, cursor_factory=RealDictCursor)
            try:
                yield conn
            finally:
                conn.close()
        except ImportError:
            raise RuntimeError("psycopg2 is required when using a PostgreSQL DATABASE_URL. Please run: pip install psycopg2-binary")
    else:
        # Safety enforcement: Block silent SQLite fallback in production / on Vercel
        if settings.IS_PRODUCTION or settings.IS_VERCEL:
            raise RuntimeError(
                "CRITICAL: DATABASE_URL environment variable is mandatory in production / on Vercel. "
                "SQLite fallback is disabled in production to protect data integrity. "
                "Please configure your Neon PostgreSQL connection string (DATABASE_URL) in Vercel Project Settings."
            )
        # SQLite (local development only)
        path = (settings.DATABASE_URL or "").replace("sqlite:///", "")
        if not path:
            path = os.path.join(BASE_DIR, "leads.db")
        elif not os.path.isabs(path):
            path = os.path.join(BASE_DIR, path)
        conn = sqlite3.connect(path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def init_database() -> None:
    """Ensures tables, indexes, and migrations exist."""
    if (settings.IS_PRODUCTION or settings.IS_VERCEL) and not is_postgres():
        raise RuntimeError(
            "CRITICAL: DATABASE_URL is not set for PostgreSQL in production / on Vercel. "
            "Cannot initialize SQLite database in production."
        )
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_postgres():
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    business_name TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    source_name TEXT,
                    source_url TEXT,
                    location TEXT,
                    date_found TEXT,
                    category TEXT DEFAULT 'Uncategorized',
                    buying_intent TEXT DEFAULT 'Unclear',
                    relevance TEXT DEFAULT 'Pending',
                    summary TEXT,
                    evidence TEXT,
                    lead_score INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'Low',
                    score_breakdown TEXT,
                    score_explanation TEXT,
                    status TEXT DEFAULT 'unprocessed',
                    error_message TEXT,
                    is_exported INTEGER DEFAULT 0,
                    exported_at TIMESTAMP,
                    record_type TEXT DEFAULT 'discovered',
                    verification_status TEXT DEFAULT 'unverified',
                    source_title TEXT,
                    publication_date TEXT,
                    verified_at TIMESTAMP,
                    verification_notes TEXT,
                    provider_name TEXT,
                    source_domain TEXT,
                    discovered_at TIMESTAMP,
                    is_live_discovery INTEGER DEFAULT 0,
                    search_query TEXT,
                    evidence_text TEXT,
                    source_fetch_status TEXT,
                    source_page_type TEXT,
                    source_verified_at TIMESTAMP,
                    source_evidence_snippet TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    analyzed_at TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_lead ON leads(business_name, requirement);
                CREATE INDEX IF NOT EXISTS idx_status ON leads(status);
                CREATE INDEX IF NOT EXISTS idx_category ON leads(category);
                CREATE INDEX IF NOT EXISTS idx_priority ON leads(priority);
                CREATE INDEX IF NOT EXISTS idx_relevance ON leads(relevance);
                CREATE INDEX IF NOT EXISTS idx_is_exported ON leads(is_exported);
                CREATE INDEX IF NOT EXISTS idx_record_type ON leads(record_type);
                CREATE INDEX IF NOT EXISTS idx_verification_status ON leads(verification_status);
                CREATE INDEX IF NOT EXISTS idx_source_page_type ON leads(source_page_type);

                -- Idempotent column migrations for existing PostgreSQL tables
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS provider_name TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_domain TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMP;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS is_live_discovery INTEGER DEFAULT 0;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS search_query TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS evidence_text TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_fetch_status TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_page_type TEXT;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_verified_at TIMESTAMP;
                ALTER TABLE leads ADD COLUMN IF NOT EXISTS source_evidence_snippet TEXT;

                CREATE TABLE IF NOT EXISTS discovery_staging (
                    id SERIAL PRIMARY KEY,
                    business_name TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    source_name TEXT,
                    source_url TEXT,
                    location TEXT,
                    date_found TEXT,
                    category TEXT,
                    service TEXT,
                    source_domain TEXT,
                    source_title TEXT,
                    publication_date TEXT,
                    verification_status TEXT,
                    record_type TEXT,
                    is_live_discovery INTEGER DEFAULT 0,
                    provider_name TEXT,
                    discovered_at TEXT,
                    evidence_text TEXT,
                    search_query TEXT,
                    source_fetch_status TEXT,
                    source_page_type TEXT,
                    source_verified_at TEXT,
                    source_evidence_snippet TEXT,
                    buying_intent TEXT,
                    relevance TEXT,
                    summary TEXT,
                    evidence TEXT,
                    lead_score INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'Low',
                    score_breakdown TEXT,
                    score_explanation TEXT,
                    analysis_status TEXT,
                    existing_lead_id INTEGER,
                    ingest_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()
        else:
            # SQLite initialization
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    source_name TEXT,
                    source_url TEXT,
                    location TEXT,
                    date_found TEXT,
                    category TEXT DEFAULT 'Uncategorized',
                    buying_intent TEXT DEFAULT 'Unclear',
                    relevance TEXT DEFAULT 'Pending',
                    summary TEXT,
                    evidence TEXT,
                    lead_score INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'Low',
                    score_breakdown TEXT,
                    score_explanation TEXT,
                    status TEXT DEFAULT 'unprocessed',
                    error_message TEXT,
                    is_exported INTEGER DEFAULT 0,
                    exported_at TIMESTAMP,
                    record_type TEXT DEFAULT 'discovered',
                    verification_status TEXT DEFAULT 'unverified',
                    source_title TEXT,
                    publication_date TEXT,
                    verified_at TIMESTAMP,
                    verification_notes TEXT,
                    source_fetch_status TEXT,
                    source_page_type TEXT,
                    source_verified_at TIMESTAMP,
                    source_evidence_snippet TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    analyzed_at TIMESTAMP
                );
                """
            )
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_lead ON leads(business_name, requirement);")
            cursor.execute("PRAGMA table_info(leads)")
            existing_cols = [row[1] for row in cursor.fetchall()]
            if "is_exported" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN is_exported INTEGER DEFAULT 0")
            if "exported_at" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN exported_at TIMESTAMP")
            if "record_type" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN record_type TEXT DEFAULT 'discovered'")
            if "verification_status" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN verification_status TEXT DEFAULT 'unverified'")
            if "source_title" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_title TEXT")
            if "publication_date" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN publication_date TEXT")
            if "verified_at" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN verified_at TIMESTAMP")
            if "verification_notes" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN verification_notes TEXT")
            if "provider_name" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN provider_name TEXT")
            if "source_domain" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_domain TEXT")
            if "discovered_at" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN discovered_at TIMESTAMP")
            if "is_live_discovery" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN is_live_discovery INTEGER DEFAULT 0")
            if "search_query" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN search_query TEXT")
            if "evidence_text" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN evidence_text TEXT")
            if "source_fetch_status" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_fetch_status TEXT")
            if "source_page_type" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_page_type TEXT")
            if "source_verified_at" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_verified_at TIMESTAMP")
            if "source_evidence_snippet" not in existing_cols:
                cursor.execute("ALTER TABLE leads ADD COLUMN source_evidence_snippet TEXT")

            # 1. Idempotent classification of demo records (IDs 1-24)
            cursor.execute(
                """
                UPDATE leads
                SET record_type = 'demo',
                    verification_status = 'demo',
                    verification_notes = 'Pre-seeded demonstration record'
                WHERE id BETWEEN 1 AND 24
                  AND (record_type IS NULL OR record_type != 'demo' OR verification_status != 'demo');
                """
            )

            # 2. Idempotent classification of user uploaded records (IDs 25, 26, 27)
            cursor.execute(
                """
                UPDATE leads
                SET record_type = 'uploaded',
                    verification_status = 'unverified',
                    verification_notes = 'User-uploaded dataset from sample_leads.csv; unverified'
                WHERE id IN (25, 26, 27)
                  AND (record_type IS NULL OR record_type != 'uploaded' OR verification_status != 'unverified');
                """
            )

            # 3. Idempotent classification of historical test auto-ingested records (IDs 253 to 316)
            cursor.execute(
                """
                UPDATE leads
                SET record_type = 'sample',
                    verification_status = 'unverified',
                    verification_notes = 'Auto-ingested during previous test from sample directory; unverified source'
                WHERE id > 27 AND id <= 316
                  AND (record_type IS NULL OR record_type NOT IN ('discovered', 'live_discovery'))
                  AND (verification_notes IS NULL OR verification_notes = '');
                """
            )

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON leads(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON leads(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON leads(priority);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_relevance ON leads(relevance);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_exported ON leads(is_exported);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_record_type ON leads(record_type);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_verification_status ON leads(verification_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source_page_type ON leads(source_page_type);")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS discovery_staging (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    business_name TEXT NOT NULL,
                    requirement TEXT NOT NULL,
                    source_name TEXT,
                    source_url TEXT,
                    location TEXT,
                    date_found TEXT,
                    category TEXT,
                    service TEXT,
                    source_domain TEXT,
                    source_title TEXT,
                    publication_date TEXT,
                    verification_status TEXT,
                    record_type TEXT,
                    is_live_discovery INTEGER DEFAULT 0,
                    provider_name TEXT,
                    discovered_at TEXT,
                    evidence_text TEXT,
                    search_query TEXT,
                    source_fetch_status TEXT,
                    source_page_type TEXT,
                    source_verified_at TEXT,
                    source_evidence_snippet TEXT,
                    buying_intent TEXT,
                    relevance TEXT,
                    summary TEXT,
                    evidence TEXT,
                    lead_score INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'Low',
                    score_breakdown TEXT,
                    score_explanation TEXT,
                    analysis_status TEXT,
                    existing_lead_id INTEGER,
                    ingest_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()


def get_leads(
    search: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    buying_intent: Optional[str] = None,
    relevance: Optional[str] = None,
    status: Optional[str] = None,
    is_exported: Optional[int] = None,
    record_type: Optional[str] = None,
    verification_status: Optional[str] = None,
    source_page_type: Optional[str] = None,
    is_live_discovery: Optional[int] = None,
    live_only: bool = False,
    order_by: str = "id_asc",
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Retrieves filtered and paginated leads along with total matching count.
    """
    init_database()
    conditions = []
    params = []
    param_char = "%s" if is_postgres() else "?"

    if live_only:
        conditions.append(
            "(record_type IN ('discovered', 'live_discovery') "
            "AND record_type NOT IN ('demo', 'sample', 'uploaded') "
            "AND is_live_discovery = 1 "
            "AND status = 'processed' "
            "AND relevance = 'Relevant' "
            "AND (source_url IS NOT NULL AND TRIM(source_url) != '') "
            "AND (evidence IS NOT NULL AND TRIM(evidence) != ''))"
        )
    else:
        if is_live_discovery is not None and not hasattr(is_live_discovery, "default"):
            try:
                conditions.append(f"is_live_discovery = {param_char}")
                params.append(int(is_live_discovery))
            except (ValueError, TypeError):
                pass

        if isinstance(record_type, str) and record_type.strip() and record_type != "All":
            rt = record_type.strip()
            if rt in ("discovered", "live_discovery"):
                conditions.append(f"(record_type = {param_char} OR record_type = {param_char})")
                params.extend(["discovered", "live_discovery"])
            else:
                conditions.append(f"record_type = {param_char}")
                params.append(rt)

    if isinstance(search, str) and search.strip():
        term = f"%{search.strip().lower()}%"
        conditions.append(
            f"(LOWER(business_name) LIKE {param_char} OR LOWER(requirement) LIKE {param_char} OR LOWER(location) LIKE {param_char} OR LOWER(COALESCE(summary, '')) LIKE {param_char})"
        )
        params.extend([term, term, term, term])

    if isinstance(category, str) and category.strip() and category != "All":
        conditions.append(f"category = {param_char}")
        params.append(category.strip())

    if isinstance(priority, str) and priority.strip() and priority != "All":
        conditions.append(f"priority = {param_char}")
        params.append(priority.strip())

    if isinstance(buying_intent, str) and buying_intent.strip() and buying_intent != "All":
        conditions.append(f"buying_intent = {param_char}")
        params.append(buying_intent.strip())

    if isinstance(relevance, str) and relevance.strip() and relevance != "All":
        conditions.append(f"relevance = {param_char}")
        params.append(relevance.strip())

    if isinstance(status, str) and status.strip() and status != "All":
        conditions.append(f"status = {param_char}")
        params.append(status.strip())

    if is_exported is not None and not hasattr(is_exported, "default"):
        try:
            if isinstance(is_exported, str) and not is_exported.isdigit():
                norm_exp = is_exported.strip().lower()
                val = 1 if norm_exp in ("exported", "true") else (0 if norm_exp in ("not exported", "unexported", "false") else None)
            else:
                val = int(is_exported)
            if val is not None:
                conditions.append(f"is_exported = {param_char}")
                params.append(val)
        except (ValueError, TypeError):
            pass

    if isinstance(verification_status, str) and verification_status.strip() and verification_status != "All":
        conditions.append(f"verification_status = {param_char}")
        params.append(verification_status.strip())

    if isinstance(source_page_type, str) and source_page_type.strip() and source_page_type != "All":
        spt = source_page_type.strip().lower()
        if spt in ("unknown", "pending", "uninspected"):
            conditions.append(f"(source_page_type = {param_char} OR source_page_type IS NULL)")
            params.append("unknown")
        else:
            conditions.append(f"source_page_type = {param_char}")
            params.append(source_page_type.strip())

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sort_clause = SAFE_ORDER_BY.get(order_by.strip().lower(), "id ASC") if isinstance(order_by, str) else "id ASC"
    limit_val = int(limit) if isinstance(limit, (int, str)) and str(limit).isdigit() else 50
    skip_val = int(skip) if isinstance(skip, (int, str)) and str(skip).isdigit() else 0

    with get_connection() as conn:
        cursor = conn.cursor()
        # Count total
        count_sql = f"SELECT COUNT(*) FROM leads{where_clause}"
        cursor.execute(count_sql, params)
        row = cursor.fetchone()
        total = row[0] if isinstance(row, (list, tuple)) else row.get("count", 0) if isinstance(row, dict) else row[0]

        # Fetch page
        data_sql = f"SELECT * FROM leads{where_clause} ORDER BY {sort_clause} LIMIT {param_char} OFFSET {param_char}"
        cursor.execute(data_sql, params + [limit_val, skip_val])
        rows = cursor.fetchall()

        results = []
        for r in rows:
            d = dict(r)
            # Parse score_breakdown JSON if string
            if isinstance(d.get("score_breakdown"), str) and d["score_breakdown"]:
                try:
                    d["score_breakdown"] = json.loads(d["score_breakdown"])
                except Exception:
                    pass
            results.append(d)

        return results, total


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    """Returns a single lead by ID or None."""
    init_database()
    param_char = "%s" if is_postgres() else "?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM leads WHERE id = {param_char}", (lead_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("score_breakdown"), str) and d["score_breakdown"]:
            try:
                d["score_breakdown"] = json.loads(d["score_breakdown"])
            except Exception:
                pass
        return d


def get_lead_by_name_and_req(business_name: str, requirement: str) -> Optional[Dict[str, Any]]:
    """Looks up a lead by unique business_name and requirement."""
    init_database()
    param_char = "%s" if is_postgres() else "?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM leads WHERE business_name = {param_char} AND requirement = {param_char}",
            (business_name.strip(), requirement.strip()),
        )
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("score_breakdown"), str) and d["score_breakdown"]:
            try:
                d["score_breakdown"] = json.loads(d["score_breakdown"])
            except Exception:
                pass
        return d


def insert_lead(
    business_name: str,
    requirement: str,
    source_name: str = "Web Discovery",
    source_url: str = "",
    location: str = "",
    date_found: str = "",
    status: str = "unprocessed",
    record_type: str = "discovered",
    verification_status: str = "unverified",
    source_title: str = "",
    publication_date: str = "",
    verified_at: Optional[str] = None,
    verification_notes: str = "",
    provider_name: str = "",
    source_domain: str = "",
    discovered_at: Optional[str] = None,
    is_live_discovery: bool = False,
    search_query: str = "",
    evidence_text: str = "",
    source_fetch_status: Optional[str] = None,
    source_page_type: Optional[str] = None,
    source_verified_at: Optional[str] = None,
    source_evidence_snippet: Optional[str] = None,
) -> Tuple[bool, Optional[int], str]:
    """
    Inserts a single lead with deduplication on (business_name, requirement).
    Returns (success, lead_id, message).
    """
    init_database()
    param_char = "%s" if is_postgres() else "?"
    norm_verified_at = verified_at if verified_at and str(verified_at).strip() else None
    norm_discovered_at = discovered_at if discovered_at and str(discovered_at).strip() else None
    norm_source_verified_at = source_verified_at if source_verified_at and str(source_verified_at).strip() else None

    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            live_disc_val = 1 if (is_live_discovery or record_type == "live_discovery") else 0
            if is_postgres():
                cursor.execute(
                    """
                    INSERT INTO leads (
                        business_name, requirement, source_name, source_url, location, date_found, status, is_exported,
                        record_type, verification_status, source_title, publication_date, verified_at, verification_notes,
                        provider_name, source_domain, discovered_at, is_live_discovery, search_query, evidence_text,
                        source_fetch_status, source_page_type, source_verified_at, source_evidence_snippet
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        business_name.strip(),
                        requirement.strip(),
                        source_name.strip(),
                        source_url.strip(),
                        location.strip(),
                        date_found.strip(),
                        status,
                        record_type.strip(),
                        verification_status.strip(),
                        source_title.strip(),
                        publication_date.strip(),
                        norm_verified_at,
                        verification_notes.strip(),
                        provider_name.strip(),
                        source_domain.strip(),
                        norm_discovered_at,
                        live_disc_val,
                        search_query.strip(),
                        evidence_text.strip(),
                        source_fetch_status,
                        source_page_type,
                        norm_source_verified_at,
                        source_evidence_snippet,
                    ),
                )
                new_id = cursor.fetchone()["id"]
            else:
                cursor.execute(
                    """
                    INSERT INTO leads (
                        business_name, requirement, source_name, source_url, location, date_found, status, is_exported,
                        record_type, verification_status, source_title, publication_date, verified_at, verification_notes,
                        provider_name, source_domain, discovered_at, is_live_discovery, search_query, evidence_text,
                        source_fetch_status, source_page_type, source_verified_at, source_evidence_snippet
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        business_name.strip(),
                        requirement.strip(),
                        source_name.strip(),
                        source_url.strip(),
                        location.strip(),
                        date_found.strip(),
                        status,
                        record_type.strip(),
                        verification_status.strip(),
                        source_title.strip(),
                        publication_date.strip(),
                        norm_verified_at,
                        verification_notes.strip(),
                        provider_name.strip(),
                        source_domain.strip(),
                        norm_discovered_at,
                        live_disc_val,
                        search_query.strip(),
                        evidence_text.strip(),
                        source_fetch_status,
                        source_page_type,
                        norm_source_verified_at,
                        source_evidence_snippet,
                    ),
                )
                new_id = cursor.lastrowid
            conn.commit()
            return True, new_id, "Lead inserted successfully."
        except sqlite3.IntegrityError:
            existing_id = None
            try:
                cursor.execute(
                    f"SELECT id FROM leads WHERE business_name = {param_char} AND requirement = {param_char}",
                    (business_name.strip(), requirement.strip()),
                )
                row = cursor.fetchone()
                if row:
                    existing_id = row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
            except Exception:
                pass
            return False, existing_id, "A lead with this business name and requirement already exists."
        except Exception as e:
            # Check for PostgreSQL psycopg2.IntegrityError or general unique constraint error
            is_unique_violation = False
            try:
                import psycopg2
                if isinstance(e, psycopg2.IntegrityError):
                    is_unique_violation = True
            except ImportError:
                pass

            if not is_unique_violation:
                err_str = str(e).lower()
                is_unique_violation = "unique" in err_str or "duplicate" in err_str or "idx_unique_lead" in err_str

            if is_unique_violation:
                existing_id = None
                try:
                    # In PostgreSQL, an aborted transaction block requires rollback before executing a new query
                    if is_postgres():
                        conn.rollback()
                    cursor.execute(
                        f"SELECT id FROM leads WHERE business_name = {param_char} AND requirement = {param_char}",
                        (business_name.strip(), requirement.strip()),
                    )
                    row = cursor.fetchone()
                    if row:
                        existing_id = row["id"] if isinstance(row, dict) or hasattr(row, "keys") else row[0]
                except Exception:
                    pass
                return False, existing_id, "A lead with this business name and requirement already exists."
            return False, None, f"Database error: {str(e)}"


def update_lead_analysis(
    lead_id: int,
    ai_analysis: Dict[str, Any],
    scoring: Dict[str, Any],
) -> None:
    """Updates a lead record with genuine AI classification and explainable score."""
    init_database()
    param_char = "%s" if is_postgres() else "?"
    bd = scoring.get("score_breakdown") or scoring.get("breakdown") or {}
    bd_str = json.dumps(bd) if isinstance(bd, (dict, list)) else str(bd)
    exp = scoring.get("explanation") or scoring.get("score_explanation") or ""
    exp_str = json.dumps(exp) if isinstance(exp, (dict, list)) else str(exp)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE leads
            SET category = {param_char},
                buying_intent = {param_char},
                relevance = {param_char},
                summary = {param_char},
                evidence = {param_char},
                lead_score = {param_char},
                priority = {param_char},
                score_breakdown = {param_char},
                score_explanation = {param_char},
                status = 'processed',
                error_message = NULL,
                analyzed_at = CURRENT_TIMESTAMP
            WHERE id = {param_char}
            """,
            (
                ai_analysis.get("category", "Not Relevant"),
                ai_analysis.get("buying_intent", "Unclear"),
                ai_analysis.get("business_relevance", "Not Relevant"),
                ai_analysis.get("summary", ""),
                ai_analysis.get("evidence", ""),
                scoring.get("total_score", 0),
                scoring.get("priority", "Low"),
                bd_str,
                exp_str,
                lead_id,
            ),
        )
        conn.commit()


def mark_lead_failed(lead_id: int, error_msg: str) -> None:
    """Marks a lead as failed with the genuine error message."""
    init_database()
    param_char = "%s" if is_postgres() else "?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE leads
            SET status = 'failed',
                error_message = {param_char}
            WHERE id = {param_char}
            """,
            (error_msg, lead_id),
        )
        conn.commit()


def update_source_verification(
    lead_id: int,
    fetch_status: str,
    page_type: str,
    verified_at: Optional[str] = None,
    evidence_snippet: str = "",
    verification_notes: Optional[str] = None,
    verification_status: Optional[str] = None,
) -> bool:
    """
    Updates the source-page verification fields of a lead.
    Preserves all other fields. Does NOT overwrite verification_status or
    verification_notes unless explicitly provided.
    """
    init_database()
    param_char = "%s" if is_postgres() else "?"
    if verified_at is not None:
        now_ts = verified_at
    elif page_type or fetch_status:
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    else:
        now_ts = None

    with get_connection() as conn:
        cursor = conn.cursor()
        set_clauses = [
            f"source_fetch_status = {param_char}",
            f"source_page_type = {param_char}",
            f"source_verified_at = {param_char}",
            f"source_evidence_snippet = {param_char}",
        ]
        params = [fetch_status, page_type, now_ts, evidence_snippet]

        if verification_notes is not None:
            set_clauses.append(f"verification_notes = {param_char}")
            params.append(verification_notes)

        if verification_status is not None:
            set_clauses.append(f"verification_status = {param_char}")
            params.append(verification_status)

        params.append(lead_id)
        sql = f"UPDATE leads SET {', '.join(set_clauses)} WHERE id = {param_char}"
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0


def mark_leads_as_exported(lead_ids: List[int]) -> int:
    """Marks specific lead IDs as exported."""
    if not lead_ids:
        return 0
    init_database()
    with get_connection() as conn:
        cursor = conn.cursor()
        if is_postgres():
            cursor.execute(
                """
                UPDATE leads
                SET is_exported = 1,
                    exported_at = CURRENT_TIMESTAMP
                WHERE id = ANY(%s)
                """,
                (lead_ids,),
            )
            count = cursor.rowcount
        else:
            placeholders = ",".join("?" for _ in lead_ids)
            cursor.execute(
                f"""
                UPDATE leads
                SET is_exported = 1,
                    exported_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                lead_ids,
            )
            count = cursor.rowcount
        conn.commit()
        return count


def get_dashboard_metrics() -> Dict[str, Any]:
    """Calculates aggregated metrics for dashboard display."""
    init_database()
    metrics = {
        "total_records": 0,
        "processed_records": 0,
        "unprocessed_records": 0,
        "failed_records": 0,
        "relevant_opportunities": 0,
        "high_priority_leads": 0,
        "medium_priority_leads": 0,
        "low_priority_leads": 0,
        "active_intent_leads": 0,
        "potential_intent_leads": 0,
        "unclear_intent_leads": 0,
        "not_yet_exported": 0,
        "exported_leads": 0,
        "category_counts": {},
        "priority_counts": {},
        "intent_counts": {},
        "service_breakdown": [],
        "high_priority_opportunities": [],
    }

    with get_connection() as conn:
        cursor = conn.cursor()

        def fetch_val(sql):
            cursor.execute(sql)
            r = cursor.fetchone()
            if isinstance(r, (list, tuple)):
                return r[0] if r else 0
            if isinstance(r, dict) or hasattr(r, "values"):
                vals = list(r.values())
                return vals[0] if vals else 0
            return r[0] if r else 0

        # KPI 1: Total Leads - Count all saved records from the leads table in Neon PostgreSQL
        metrics["total_records"] = fetch_val("SELECT COUNT(*) FROM leads")
        metrics["processed_records"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(status)) = 'processed'")
        metrics["unprocessed_records"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(status)) = 'unprocessed'")
        metrics["failed_records"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(status)) = 'failed'")
        metrics["relevant_opportunities"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(relevance)) = 'relevant'")

        # KPI 3: High Priority Leads - Count leads classified as high priority
        metrics["high_priority_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(priority)) = 'high'")

        # KPI 4: Medium Priority Leads - Count leads classified as medium priority
        metrics["medium_priority_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(priority)) = 'medium'")

        # Low Priority Leads
        metrics["low_priority_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(priority)) = 'low'")

        # KPI 2: Active Buying Intent - Count leads classified with active buying intent
        metrics["active_intent_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(buying_intent)) = 'active'")

        # KPI 5: Potential Buying Intent - Count leads classified as potential buying intent
        metrics["potential_intent_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(buying_intent)) = 'potential'")

        # Unclear / other intent
        metrics["unclear_intent_leads"] = fetch_val(
            "SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(buying_intent)) = 'unclear' OR buying_intent IS NULL OR TRIM(buying_intent) = ''"
        )

        # Export status
        metrics["not_yet_exported"] = fetch_val("SELECT COUNT(*) FROM leads WHERE is_exported = 0")
        metrics["exported_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE is_exported = 1")

        metrics["verified_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(verification_status)) = 'verified'")
        metrics["unverified_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(verification_status)) = 'unverified'")
        metrics["demo_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(record_type)) = 'demo'")
        metrics["discovered_leads"] = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(record_type)) IN ('discovered', 'live_discovery')")

        # Category Breakdown - Group saved leads by category
        cursor.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized') as cat, COUNT(*) as cnt
            FROM leads
            GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized')
            ORDER BY COUNT(*) DESC
            """
        )
        cat_rows = cursor.fetchall()
        metrics["category_counts"] = {
            (r["cat"] if isinstance(r, dict) or hasattr(r, "keys") else r[0]): int(r["cnt"] if isinstance(r, dict) or hasattr(r, "keys") else r[1])
            for r in cat_rows
        } if cat_rows else {}

        # Priority Breakdown
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN LOWER(TRIM(priority)) = 'high' THEN 'High'
                    WHEN LOWER(TRIM(priority)) = 'medium' THEN 'Medium'
                    WHEN LOWER(TRIM(priority)) = 'low' THEN 'Low'
                    ELSE 'Low'
                END as prio,
                COUNT(*) as cnt
            FROM leads
            GROUP BY prio
            ORDER BY cnt DESC
            """
        )
        prio_rows = cursor.fetchall()
        metrics["priority_counts"] = {
            (r["prio"] if isinstance(r, dict) or hasattr(r, "keys") else r[0]): int(r["cnt"] if isinstance(r, dict) or hasattr(r, "keys") else r[1])
            for r in prio_rows
        } if prio_rows else {}

        # Intent Breakdown
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN LOWER(TRIM(buying_intent)) = 'active' THEN 'Active'
                    WHEN LOWER(TRIM(buying_intent)) = 'potential' THEN 'Potential'
                    WHEN LOWER(TRIM(buying_intent)) = 'unclear' THEN 'Unclear'
                    ELSE 'Unclear'
                END as intent,
                COUNT(*) as cnt
            FROM leads
            GROUP BY intent
            ORDER BY cnt DESC
            """
        )
        intent_rows = cursor.fetchall()
        metrics["intent_counts"] = {
            (r["intent"] if isinstance(r, dict) or hasattr(r, "keys") else r[0]): int(r["cnt"] if isinstance(r, dict) or hasattr(r, "keys") else r[1])
            for r in intent_rows
        } if intent_rows else {}

        # Section C: Service-wise Lead Analysis
        cursor.execute(
            """
            SELECT
                COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized') as service_category,
                COUNT(*) as total_leads,
                COUNT(CASE WHEN LOWER(TRIM(priority)) = 'high' THEN 1 END) as high_priority_leads,
                COUNT(CASE WHEN LOWER(TRIM(priority)) = 'medium' THEN 1 END) as medium_priority_leads,
                COUNT(CASE WHEN LOWER(TRIM(priority)) = 'low' THEN 1 END) as low_priority_leads
            FROM leads
            GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized')
            ORDER BY total_leads DESC, high_priority_leads DESC
            """
        )
        service_rows = cursor.fetchall()
        metrics["service_breakdown"] = [
            {
                "service_category": str(r["service_category"] if hasattr(r, "keys") or isinstance(r, dict) else r[0]),
                "total_leads": int(r["total_leads"] if hasattr(r, "keys") or isinstance(r, dict) else r[1]),
                "high_priority_leads": int(r["high_priority_leads"] if hasattr(r, "keys") or isinstance(r, dict) else r[2]),
                "medium_priority_leads": int(r["medium_priority_leads"] if hasattr(r, "keys") or isinstance(r, dict) else r[3]),
                "low_priority_leads": int(r["low_priority_leads"] if hasattr(r, "keys") or isinstance(r, dict) else r[4]),
            }
            for r in service_rows
        ] if service_rows else []

        # Section D: High-Priority Opportunities
        cursor.execute(
            """
            SELECT
                id,
                business_name,
                category,
                buying_intent,
                lead_score,
                relevance,
                priority,
                location,
                date_found,
                is_exported,
                summary
            FROM leads
            WHERE LOWER(TRIM(priority)) = 'high'
            ORDER BY lead_score DESC, id DESC
            LIMIT 10
            """
        )
        high_rows = cursor.fetchall()
        metrics["high_priority_opportunities"] = [
            {
                "id": int(r["id"] if hasattr(r, "keys") or isinstance(r, dict) else r[0]),
                "business_name": str(r["business_name"] if hasattr(r, "keys") or isinstance(r, dict) else r[1]),
                "category": str(r["category"] if hasattr(r, "keys") or isinstance(r, dict) else r[2] or "Uncategorized"),
                "buying_intent": str(r["buying_intent"] if hasattr(r, "keys") or isinstance(r, dict) else r[3] or "Unclear"),
                "lead_score": int(r["lead_score"] if hasattr(r, "keys") or isinstance(r, dict) else r[4] or 0),
                "relevance": str(r["relevance"] if hasattr(r, "keys") or isinstance(r, dict) else r[5] or "Pending"),
                "priority": str(r["priority"] if hasattr(r, "keys") or isinstance(r, dict) else r[6] or "High"),
                "location": str(r["location"] if hasattr(r, "keys") or isinstance(r, dict) else (r[7] if len(r) > 7 else "") or ""),
                "date_found": str(r["date_found"] if hasattr(r, "keys") or isinstance(r, dict) else (r[8] if len(r) > 8 else "") or ""),
                "is_exported": int(r["is_exported"] if hasattr(r, "keys") or isinstance(r, dict) else (r[9] if len(r) > 9 else 0) or 0),
                "summary": str(r["summary"] if hasattr(r, "keys") or isinstance(r, dict) else (r[10] if len(r) > 10 else "") or ""),
            }
            for r in high_rows
        ] if high_rows else []

    return metrics

    return metrics


def get_export_dataframe(
    scope: str = "all",
    include_historical: bool = False,
    lead_ids: Optional[List[int]] = None,
) -> pd.DataFrame:
    """
    Returns filtered DataFrame sorted by id ASC for CSV and Excel export.
    Excludes historical demo, sample, and uploaded records from all normal organization exports,
    ensuring only genuine live-discovered, processed, relevant, and verified leads are exported.
    Prevents duplicate exports when scope='unexported'. Supports explicit lead_ids filtering.
    """
    init_database()

    # Strict qualification condition for genuine live-discovered leads:
    # 1. record_type IN ('discovered', 'live_discovery') and NOT IN ('demo', 'sample', 'uploaded')
    # 2. is_live_discovery = 1
    # 3. status = 'processed' (completed AI analysis)
    # 4. relevance = 'Relevant' (excludes unqualified/failed leads)
    # 5. Non-empty source URL and non-empty supporting evidence
    live_qualified_filter = (
        "record_type IN ('discovered', 'live_discovery') "
        "AND record_type NOT IN ('demo', 'sample', 'uploaded') "
        "AND is_live_discovery = 1 "
        "AND status = 'processed' "
        "AND relevance = 'Relevant' "
        "AND (source_url IS NOT NULL AND TRIM(source_url) != '') "
        "AND (evidence IS NOT NULL AND TRIM(evidence) != '')"
    )

    scope_clean = str(getattr(scope, "default", scope)).lower().strip() if hasattr(scope, "default") else str(scope).lower().strip()

    params: Any = None
    if lead_ids is not None:
        if len(lead_ids) == 0:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM leads WHERE 1=0")
                colnames = [desc[0] for desc in cursor.description]
                return pd.DataFrame(columns=colnames)

        if is_postgres():
            id_filter = "id = ANY(%s)"
            params = (lead_ids,)
        else:
            placeholders = ",".join("?" for _ in lead_ids)
            id_filter = f"id IN ({placeholders})"
            params = tuple(lead_ids)

        if include_historical:
            where = f"WHERE {id_filter}"
        else:
            where = f"WHERE {id_filter} AND record_type NOT IN ('demo', 'sample')"
    else:
        if include_historical and scope_clean == "all":
            # Internal test/system debug bypass only
            where = ""
        elif scope_clean == "unexported":
            # Prevent duplicate exports: only genuine leads with is_exported = 0
            where = f"WHERE {live_qualified_filter} AND is_exported = 0"
        elif scope_clean in ("processed", "all"):
            # Normal organization export: all genuine live-discovered, processed, relevant leads
            where = f"WHERE {live_qualified_filter}"
        elif scope_clean == "high_medium":
            where = f"WHERE {live_qualified_filter} AND priority IN ('High', 'Medium')"
        elif scope_clean == "high_priority":
            where = f"WHERE {live_qualified_filter} AND priority = 'High'"
        elif scope_clean == "relevant":
            where = f"WHERE {live_qualified_filter}"
        else:
            where = f"WHERE {live_qualified_filter}"

    with get_connection() as conn:
        cursor = conn.cursor()
        if params is not None:
            cursor.execute(f"SELECT * FROM leads {where} ORDER BY id ASC", params)
        else:
            cursor.execute(f"SELECT * FROM leads {where} ORDER BY id ASC")
        rows = cursor.fetchall()
        if not rows:
            cursor.execute("SELECT * FROM leads WHERE 1=0")
            colnames = [desc[0] for desc in cursor.description]
            return pd.DataFrame(columns=colnames)
        return pd.DataFrame([dict(r) for r in rows])


def save_discovery_staging_batch(candidates: List[Dict[str, Any]]) -> None:
    """Overwrites discovery_staging with the current batch of discovered candidates. Only genuine live discoveries are staged."""
    init_database()
    param_char = "%s" if is_postgres() else "?"
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM discovery_staging")
        for cand in candidates:
            # Guardrail: Never stage static demonstration benchmarks or sample records
            if not cand.get("is_live_discovery") or cand.get("record_type") in ("demo", "sample") or cand.get("verification_status") == "demo":
                continue

            breakdown_str = json.dumps(cand.get("score_breakdown", {})) if isinstance(cand.get("score_breakdown"), dict) else str(cand.get("score_breakdown") or "")
            explanation_str = json.dumps(cand.get("score_explanation", {})) if isinstance(cand.get("score_explanation"), dict) else str(cand.get("score_explanation") or "")
            live_val = 1 if cand.get("is_live_discovery") else 0

            cursor.execute(
                f"""
                INSERT INTO discovery_staging (
                    business_name, requirement, source_name, source_url, location, date_found,
                    category, service, source_domain, source_title, publication_date,
                    verification_status, record_type, is_live_discovery, provider_name,
                    discovered_at, evidence_text, search_query, source_fetch_status,
                    source_page_type, source_verified_at, source_evidence_snippet,
                    buying_intent, relevance, summary, evidence, lead_score, priority,
                    score_breakdown, score_explanation, analysis_status, existing_lead_id, ingest_status
                )
                VALUES (
                    {param_char}, {param_char}, {param_char}, {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char}, {param_char}, {param_char}, {param_char},
                    {param_char}, {param_char}, {param_char}, {param_char}, {param_char}
                )
                """,
                (
                    cand.get("business_name", ""),
                    cand.get("requirement", ""),
                    cand.get("source_name", ""),
                    cand.get("source_url", ""),
                    cand.get("location", ""),
                    cand.get("date_found") or cand.get("publication_date") or "",
                    cand.get("category", ""),
                    cand.get("service", ""),
                    cand.get("source_domain", ""),
                    cand.get("source_title", ""),
                    cand.get("publication_date", ""),
                    cand.get("verification_status", "unverified"),
                    cand.get("record_type", "live_discovery"),
                    live_val,
                    cand.get("provider_name", ""),
                    cand.get("discovered_at", ""),
                    cand.get("evidence_text", ""),
                    cand.get("search_query", ""),
                    cand.get("source_fetch_status", ""),
                    cand.get("source_page_type", ""),
                    cand.get("source_verified_at", ""),
                    cand.get("source_evidence_snippet", ""),
                    cand.get("buying_intent", "Unclear"),
                    cand.get("relevance", "Pending"),
                    cand.get("summary", ""),
                    cand.get("evidence", ""),
                    cand.get("lead_score", 0),
                    cand.get("priority", "Low"),
                    breakdown_str,
                    explanation_str,
                    cand.get("analysis_status", "pending"),
                    cand.get("existing_lead_id"),
                    cand.get("ingest_status", "unprocessed"),
                ),
            )
        conn.commit()


def get_discovery_staging_batch() -> List[Dict[str, Any]]:
    """Retrieves all genuine live candidates currently staged in discovery_staging with live deduplication checking."""
    init_database()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM discovery_staging WHERE is_live_discovery = 1 AND record_type NOT IN ('demo', 'sample') ORDER BY id ASC"
        )
        rows = cursor.fetchall()
        candidates = []
        for r in rows:
            item = dict(r)
            for json_col in ("score_breakdown", "score_explanation"):
                if item.get(json_col) and isinstance(item[json_col], str):
                    try:
                        item[json_col] = json.loads(item[json_col])
                    except Exception:
                        pass
            # Live deduplication check against leads table
            existing = get_lead_by_name_and_req(item.get("business_name", ""), item.get("requirement", ""))
            if existing:
                item["existing_lead_id"] = existing["id"]
                item["id"] = existing["id"]
                item["ingest_status"] = "already_exists"
            else:
                item["existing_lead_id"] = None
                item["ingest_status"] = item.get("ingest_status") or "unprocessed"
            candidates.append(item)
        return candidates


def clear_discovery_staging_batch() -> None:
    """Clears all records in discovery_staging."""
    init_database()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM discovery_staging")
        conn.commit()


def save_staged_batch_to_pipeline(candidates: Optional[List[Dict[str, Any]]] = None) -> Tuple[int, int, str]:
    """
    Persists staged discovery candidates into the main `leads` table.
    Skips duplicates, assigns processed status with AI analysis and lead score,
    and clears the staging table upon success.
    Returns (saved_count, duplicates_skipped, message).
    """
    init_database()
    if candidates is None:
        candidates = get_discovery_staging_batch()

    if not candidates:
        return 0, 0, "No candidates in discovery batch to save."

    saved_count = 0
    duplicate_count = 0

    for cand in candidates:
        b_name = cand.get("business_name", "").strip()
        req = cand.get("requirement", "").strip()
        if not b_name or not req:
            continue

        # Guardrail (Requirement B.2): Do not save static benchmarks, demo records, sample records or unqualified records as genuine leads
        if (
            not cand.get("is_live_discovery")
            or cand.get("record_type") in ("demo", "sample")
            or cand.get("verification_status") == "demo"
            or str(cand.get("relevance", "")).strip().lower() in ("not relevant", "unqualified")
            or str(cand.get("buying_intent", "")).strip().lower() in ("unqualified",)
        ):
            continue

        # Check if already exists in leads
        existing = get_lead_by_name_and_req(b_name, req)
        if existing:
            duplicate_count += 1
            continue

        cand_rt = cand.get("record_type")
        saved_rt = "discovered" if (not cand_rt or cand_rt in ("live_discovery", "discovered")) else cand_rt

        ok, new_id, msg = insert_lead(
            business_name=b_name,
            requirement=req,
            source_name=cand.get("source_name", "Web Discovery"),
            source_url=cand.get("source_url", ""),
            location=cand.get("location", ""),
            date_found=cand.get("date_found") or cand.get("publication_date") or datetime.date.today().strftime("%Y-%m-%d"),
            status="processed",
            record_type=saved_rt,
            verification_status=cand.get("verification_status", "unverified"),
            source_title=cand.get("source_title", ""),
            publication_date=cand.get("publication_date", ""),
            verified_at=cand.get("verified_at"),
            verification_notes=cand.get("verification_notes", ""),
            provider_name=cand.get("provider_name", ""),
            source_domain=cand.get("source_domain", ""),
            discovered_at=cand.get("discovered_at"),
            is_live_discovery=True,
            search_query=cand.get("search_query", ""),
            evidence_text=cand.get("evidence_text", ""),
            source_fetch_status=cand.get("source_fetch_status"),
            source_page_type=cand.get("source_page_type"),
            source_verified_at=cand.get("source_verified_at"),
            source_evidence_snippet=cand.get("source_evidence_snippet"),
        )

        if ok and new_id:
            ai_analysis = {
                "category": cand.get("category", "Not Relevant"),
                "buying_intent": cand.get("buying_intent", "Unclear"),
                "business_relevance": cand.get("relevance", "Relevant"),
                "summary": cand.get("summary", ""),
                "evidence": cand.get("evidence", ""),
            }
            breakdown = cand.get("score_breakdown")
            if isinstance(breakdown, str):
                try:
                    breakdown = json.loads(breakdown)
                except Exception:
                    breakdown = {}
            explanation = cand.get("score_explanation")
            if isinstance(explanation, str):
                try:
                    explanation = json.loads(explanation)
                except Exception:
                    explanation = {}

            scoring = {
                "total_score": cand.get("lead_score", 0),
                "priority": cand.get("priority", "Low"),
                "breakdown": breakdown or {},
                "explanation": explanation or {},
            }
            update_lead_analysis(new_id, ai_analysis, scoring)
            saved_count += 1
        else:
            duplicate_count += 1

    clear_discovery_staging_batch()
    message = f"Saved {saved_count} lead(s) to pipeline ({duplicate_count} duplicate(s) skipped)."
    return saved_count, duplicate_count, message
