"""
database.py - SQLite Database Management Layer

Handles local SQLite storage, automatic schema creation, lead deduplication,
batch retrieval, and analytical aggregation queries.

Note on Cloud Deployment:
Streamlit Community Cloud runs apps inside ephemeral containers. While SQLite is
ideal for local development and demonstration, runtime modifications to SQLite files
are not guaranteed to persist across cloud container restarts/sleep cycles.
"""

from typing import List, Dict, Any, Optional, Tuple
import sqlite3
import os
import json
import contextlib
import pandas as pd
import data_processor

__all__ = [
    "DB_PATH",
    "SAFE_ORDER_BY_OPTIONS",
    "get_db",
    "init_db",
    "insert_leads_from_df",
    "seed_demo_leads_if_empty",
    "get_unprocessed_leads",
    "update_lead_analysis",
    "mark_lead_failed",
    "mark_leads_as_exported",
    "get_all_leads",
    "get_dashboard_metrics",
    "reset_database",
]

# Predefined safe order options to avoid SQL injection
SAFE_ORDER_BY_OPTIONS: Dict[str, str] = {
    "id_asc": "id ASC",
    "id_desc": "id DESC",
    "score_desc": "lead_score DESC, id ASC",
    "score_asc": "lead_score ASC, id ASC",
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")


@contextlib.contextmanager
def get_db(db_path: str = DB_PATH):
    """
    Context manager that yields an active SQLite connection and guarantees
    connection closure and cleanup even on Windows file systems.
    """
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    """
    Initializes the SQLite database and creates the 'leads' table and indexes
    if they do not already exist. Called automatically on application startup.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzed_at TIMESTAMP
            );
            """
        )
        # Unique index on business_name and requirement to prevent duplicate leads
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_lead 
            ON leads(business_name, requirement);
            """
        )
        # Safe migration for existing databases: ensure is_exported and exported_at columns exist
        cursor.execute("PRAGMA table_info(leads)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        if "is_exported" not in existing_cols:
            cursor.execute("ALTER TABLE leads ADD COLUMN is_exported INTEGER DEFAULT 0")
        if "exported_at" not in existing_cols:
            cursor.execute("ALTER TABLE leads ADD COLUMN exported_at TIMESTAMP")

        # Performance indexes for common filters
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON leads(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON leads(category);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_priority ON leads(priority);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_relevance ON leads(relevance);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_exported ON leads(is_exported);")
        conn.commit()


def insert_leads_from_df(df: pd.DataFrame, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    Inserts validated leads from a DataFrame into SQLite.
    Skips rows that already exist based on the unique index.
    New leads automatically start with is_exported=0.

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    init_db(db_path)
    inserted = 0
    skipped = 0

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            try:
                cursor.execute(
                    """
                    INSERT INTO leads (
                        business_name, requirement, source_name, source_url, location, date_found, status, is_exported
                    ) VALUES (?, ?, ?, ?, ?, ?, 'unprocessed', 0)
                    """,
                    (
                        str(row.get("business_name", "")).strip(),
                        str(row.get("requirement", "")).strip(),
                        str(row.get("source_name", "")).strip(),
                        str(row.get("source_url", "")).strip(),
                        str(row.get("location", "")).strip(),
                        str(row.get("date_found", "")).strip(),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate record already exists in database
                skipped += 1
            except Exception as e:
                print(f"Error inserting row: {e}")
                skipped += 1
        conn.commit()

    return inserted, skipped


def seed_demo_leads_if_empty(csv_path: Optional[str] = None, db_path: str = DB_PATH) -> Tuple[int, int]:
    """
    Checks whether the database contains zero lead records.
    If zero, locates data/sample_leads.csv, validates it using data_processor, and
    inserts the records using insert_leads_from_df().
    Does not insert if records already exist.
    Handles missing CSV files and import errors safely.

    Returns:
        Tuple of (inserted_count, skipped_count)
    """
    init_db(db_path)

    # Check whether the database contains zero lead records
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM leads")
        record_count = cursor.fetchone()[0]

    # Do not insert records if the database already contains leads
    if record_count > 0:
        return 0, 0

    # Locate data/sample_leads.csv
    if not csv_path:
        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sample_leads.csv")

    if not os.path.exists(csv_path):
        return 0, 0

    try:
        is_valid, df, err, _ = data_processor.load_and_validate_csv(csv_path)
        if is_valid and df is not None and not df.empty:
            ins, skp = insert_leads_from_df(df, db_path=db_path)
            # The 24 demo leads start marked as already exported
            with get_db(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE leads SET is_exported = 1 WHERE business_name LIKE '%(Demo)%' OR id <= 24"
                )
                conn.commit()
            return ins, skp
    except Exception as e:
        print(f"Error auto-seeding demo leads: {e}")

    return 0, 0


def get_unprocessed_leads(limit: Optional[int] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Fetches leads with status='unprocessed' or status='failed'.
    Supports limiting the batch size (e.g. 3 or 5 for quick testing).
    """
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM leads WHERE status IN ('unprocessed', 'failed') ORDER BY id ASC"
        if limit and limit > 0:
            query += f" LIMIT {int(limit)}"
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_lead_analysis(
    lead_id: int,
    ai_analysis: Dict[str, Any],
    scoring: Dict[str, Any],
    db_path: str = DB_PATH,
) -> None:
    """
    Updates a lead record with genuine AI classification and explainable score.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE leads
            SET category = ?,
                buying_intent = ?,
                relevance = ?,
                summary = ?,
                evidence = ?,
                lead_score = ?,
                priority = ?,
                score_breakdown = ?,
                score_explanation = ?,
                status = 'processed',
                error_message = NULL,
                analyzed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                ai_analysis.get("category", "Not Relevant"),
                ai_analysis.get("buying_intent", "Unclear"),
                ai_analysis.get("business_relevance", "Not Relevant"),
                ai_analysis.get("summary", ""),
                ai_analysis.get("evidence", ""),
                scoring.get("total_score", 0),
                scoring.get("priority", "Low"),
                json.dumps(scoring.get("score_breakdown", {})),
                scoring.get("explanation", ""),
                lead_id,
            ),
        )
        conn.commit()


def mark_lead_failed(lead_id: int, error_msg: str, db_path: str = DB_PATH) -> None:
    """Marks a lead as failed with the actual error message without fabricating data."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE leads
            SET status = 'failed',
                error_message = ?
            WHERE id = ?
            """,
            (error_msg, lead_id),
        )
        conn.commit()


def mark_leads_as_exported(lead_ids: List[int], db_path: str = DB_PATH) -> int:
    """
    Marks specific lead IDs as exported (is_exported=1, exported_at=CURRENT_TIMESTAMP).
    Returns the count of rows updated.
    """
    if not lead_ids:
        return 0
    init_db(db_path)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in lead_ids)
        query = f"""
            UPDATE leads
            SET is_exported = 1,
                exported_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
        """
        cursor.execute(query, lead_ids)
        conn.commit()
        return cursor.rowcount


def get_all_leads(order_by: str = "id_asc", db_path: str = DB_PATH) -> pd.DataFrame:
    """
    Retrieves all leads from the database as a Pandas DataFrame.

    Args:
        order_by: Predefined safe sort order. Allowed options:
                  'id_asc' (default) -> ORDER BY id ASC
                  'score_desc'       -> ORDER BY lead_score DESC, id ASC
                  'id_desc'          -> ORDER BY id DESC
                  'score_asc'        -> ORDER BY lead_score ASC, id ASC
                  Any unlisted option falls back safely to 'id_asc'.
        db_path: Path to SQLite database.
    """
    init_db(db_path)
    # Whitelist validation to completely avoid SQL injection
    normalized_order = str(order_by).strip().lower()
    if normalized_order in SAFE_ORDER_BY_OPTIONS:
        clause = SAFE_ORDER_BY_OPTIONS[normalized_order]
    elif order_by in ("id ASC", "lead_score DESC, id ASC"):
        clause = order_by
    else:
        clause = "id ASC"

    with get_db(db_path) as conn:
        df = pd.read_sql_query(f"SELECT * FROM leads ORDER BY {clause}", conn)
        return df


def get_dashboard_metrics(db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Calculates aggregated metrics for the Streamlit dashboard overview.
    """
    init_db(db_path)
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
        "category_counts": {},
        "priority_counts": {},
        "intent_counts": {},
    }

    with get_db(db_path) as conn:
        cursor = conn.cursor()

        # Total counts
        cursor.execute("SELECT COUNT(*) FROM leads")
        metrics["total_records"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'processed'")
        metrics["processed_records"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'unprocessed'")
        metrics["unprocessed_records"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE status = 'failed'")
        metrics["failed_records"] = cursor.fetchone()[0]

        # Processed-specific metrics
        cursor.execute("SELECT COUNT(*) FROM leads WHERE relevance = 'Relevant' AND status = 'processed'")
        metrics["relevant_opportunities"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE priority = 'High' AND status = 'processed'")
        metrics["high_priority_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE priority = 'Medium' AND status = 'processed'")
        metrics["medium_priority_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE priority = 'Low' AND status = 'processed'")
        metrics["low_priority_leads"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM leads WHERE buying_intent = 'Active' AND status = 'processed'")
        metrics["active_intent_leads"] = cursor.fetchone()[0]

        # Category breakdowns
        cursor.execute(
            """
            SELECT category, COUNT(*) 
            FROM leads 
            WHERE status = 'processed' 
            GROUP BY category
            ORDER BY COUNT(*) DESC
            """
        )
        metrics["category_counts"] = dict(cursor.fetchall())

        # Priority counts
        cursor.execute(
            """
            SELECT priority, COUNT(*) 
            FROM leads 
            WHERE status = 'processed' 
            GROUP BY priority
            """
        )
        metrics["priority_counts"] = dict(cursor.fetchall())

        # Intent counts
        cursor.execute(
            """
            SELECT buying_intent, COUNT(*) 
            FROM leads 
            WHERE status = 'processed' 
            GROUP BY buying_intent
            """
        )
        metrics["intent_counts"] = dict(cursor.fetchall())

    return metrics


def reset_database(db_path: str = DB_PATH) -> None:
    """Clears all records from the database (for testing or full reset)."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS leads")
        conn.commit()
    init_db(db_path)
