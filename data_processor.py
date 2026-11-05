"""
data_processor.py - CSV Validation and Data Ingestion Pipeline

This module is responsible for loading, validating, sanitizing, and deduplicating
business lead requirements from both the default sample CSV and user-uploaded files.

Key Responsibilities:
1. Column Presence Validation: Ensures mandatory schema columns exist.
2. Empty Requirement Filtering: Rejects or filters records with missing/blank requirements.
3. Whitespace Sanitization: Normalizes strings and trims unwanted spaces.
4. Deduplication: Removes duplicate entries based on business name and requirement text.
5. Error Reporting: Produces detailed, beginner-friendly diagnostics for UI display.
"""

from typing import Tuple, Dict, Any, Optional
import io
import pandas as pd

# The mandatory columns required for the Lead Discovery System
REQUIRED_COLUMNS = [
    "business_name",
    "requirement",
    "source_name",
    "source_url",
    "location",
    "date_found",
]


class DataValidationError(Exception):
    """Custom exception raised when CSV schema or data validation fails."""
    pass


def load_and_validate_csv(
    file_or_path: Any,
) -> Tuple[bool, Optional[pd.DataFrame], str, Dict[str, Any]]:
    """
    Loads a CSV file from a file path or file-like object, validates its schema,
    sanitizes text, and removes duplicate or empty records.

    Args:
        file_or_path: Path string (e.g. 'data/sample_leads.csv') or
                      Streamlit UploadedFile / io.BytesIO / io.StringIO.

    Returns:
        Tuple containing:
        - is_valid (bool): True if at least one valid record was parsed.
        - df (pd.DataFrame or None): Cleaned DataFrame if valid, else None.
        - error_message (str): Explanatory error message if validation failed, else "".
        - stats (dict): Summary statistics (total_rows, valid_rows, duplicates_dropped, empty_dropped).
    """
    stats = {
        "raw_count": 0,
        "valid_count": 0,
        "duplicates_dropped": 0,
        "empty_dropped": 0,
    }

    # Step 1: Read CSV safely with fallback encoding
    try:
        if isinstance(file_or_path, str):
            df = pd.read_csv(file_or_path, encoding="utf-8")
        elif hasattr(file_or_path, "read"):
            # Could be Streamlit UploadedFile or BytesIO
            try:
                # Attempt standard UTF-8 first
                df = pd.read_csv(file_or_path, encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback to Latin-1 if non-UTF8 characters exist
                if hasattr(file_or_path, "seek"):
                    file_or_path.seek(0)
                df = pd.read_csv(file_or_path, encoding="latin-1")
        else:
            return False, None, "Invalid input: expected file path or file-like object.", stats
    except pd.errors.EmptyDataError:
        return False, None, "The uploaded CSV file is empty. Please supply a valid CSV with header and data.", stats
    except Exception as e:
        return False, None, f"Failed to parse CSV file: {str(e)}", stats

    stats["raw_count"] = len(df)

    if df.empty:
        return False, None, "The CSV file contains no data rows.", stats

    # Step 2: Validate column presence (case-insensitive strip matching)
    cleaned_columns = {col: str(col).strip().lower() for col in df.columns}
    df = df.rename(columns=cleaned_columns)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        error_msg = (
            f"CSV is missing {len(missing_cols)} required column(s): {', '.join(missing_cols)}.\n"
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}."
        )
        return False, None, error_msg, stats

    # Keep only required columns and reorder consistently
    df = df[REQUIRED_COLUMNS].copy()

    # Step 3: Whitespace trimming and string conversions
    for col in REQUIRED_COLUMNS:
        df[col] = df[col].fillna("").astype(str).str.strip()
        # Clean string representations of null
        df.loc[df[col].str.lower().isin(["nan", "none", "null", ""]), col] = ""

    # Step 4: Drop records where requirement or business_name is empty
    initial_len = len(df)
    valid_mask = (df["requirement"] != "") & (df["business_name"] != "")
    df = df[valid_mask].copy()
    empty_dropped = initial_len - len(df)
    stats["empty_dropped"] = empty_dropped

    if df.empty:
        return (
            False,
            None,
            "All rows in the CSV had empty 'requirement' or 'business_name' fields.",
            stats,
        )

    # Step 5: Deduplication based on business_name + requirement
    pre_dedup_len = len(df)
    # Deduplicate while preserving first occurrence
    df = df.drop_duplicates(subset=["business_name", "requirement"], keep="first").copy()
    duplicates_dropped = pre_dedup_len - len(df)
    stats["duplicates_dropped"] = duplicates_dropped

    # Reset index for clean numbering
    df = df.reset_index(drop=True)
    stats["valid_count"] = len(df)

    return True, df, "", stats


def validate_dataframe_schema(df: pd.DataFrame) -> Tuple[bool, str]:
    """
    Validates whether an existing in-memory DataFrame adheres to the required schema.
    """
    if df is None or df.empty:
        return False, "DataFrame is empty."
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        return False, f"Missing columns: {', '.join(missing_cols)}"
    return True, "Schema is valid."
