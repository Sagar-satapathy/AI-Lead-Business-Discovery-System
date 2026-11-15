"""
backend/services/export_service.py - CSV and Excel Export Pipeline

Generates enterprise-grade, clean CSV and styled Excel spreadsheets (.xlsx)
for CRM/ERP ingestion and procurement reporting.

Supported Scopes:
1. 'unexported': Leads with is_exported = 0 and status = 'processed'
2. 'processed': All leads with status = 'processed'
3. 'high_medium': Leads with priority IN ('High', 'Medium') and status = 'processed'
4. 'all': Complete database records
"""

from typing import Tuple, List, Dict, Any, Optional
import io
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from backend.db import get_export_dataframe, mark_leads_as_exported

EXPORT_SCOPES = ["unexported", "processed", "high_medium", "all"]

COLUMN_DISPLAY_NAMES = {
    "id": "Lead ID",
    "business_name": "Business Name",
    "record_type": "Record Type",
    "verification_status": "Verification Status",
    "category": "Service Category",
    "buying_intent": "Buying Intent",
    "relevance": "Relevance",
    "lead_score": "Lead Score (0-100)",
    "priority": "Priority",
    "summary": "AI Summary",
    "evidence": "Verbatim Evidence",
    "location": "Location",
    "date_found": "Date Discovered",
    "source_name": "Source Name",
    "source_url": "Source URL",
    "source_title": "Source Title",
    "publication_date": "Publication Date",
    "verification_notes": "Verification Notes",
    "provider_name": "Discovery Provider",
    "source_domain": "Source Domain",
    "discovered_at": "Discovered At",
    "evidence_text": "Evidence Text",
    "search_query": "Search Query",
    "status": "Processing Status",
    "is_exported": "Exported",
    "exported_at": "Exported At",
    "score_explanation": "Score Explainability",
    "requirement": "Original Requirement",
}


def get_scoped_dataframe(scope: str) -> pd.DataFrame:
    """Retrieves and prepares the DataFrame for the requested export scope."""
    scope_clean = scope.lower().strip()
    if scope_clean not in EXPORT_SCOPES:
        scope_clean = "unexported"

    df = get_export_dataframe(scope_clean)
    return df


def generate_csv_bytes(scope: str) -> Tuple[bytes, List[int], int]:
    """
    Generates a CSV export with UTF-8 BOM for universal Excel and CRM compatibility.
    Returns (csv_bytes, exported_lead_ids, record_count).
    """
    df = get_scoped_dataframe(scope)
    if df.empty:
        # Return empty CSV with standard headers
        empty_df = pd.DataFrame(columns=list(COLUMN_DISPLAY_NAMES.values()))
        csv_str = empty_df.to_csv(index=False)
        return csv_str.encode("utf-8-sig"), [], 0

    lead_ids = df["id"].tolist() if "id" in df.columns else []

    # Map column names to friendly display titles where available
    export_cols = [c for c in COLUMN_DISPLAY_NAMES.keys() if c in df.columns]
    rename_map = {c: COLUMN_DISPLAY_NAMES[c] for c in export_cols}
    df_export = df[export_cols].rename(columns=rename_map)

    # Encode with UTF-8 BOM
    csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
    return csv_bytes, lead_ids, len(df_export)


def generate_excel_bytes(scope: str) -> Tuple[bytes, List[int], int]:
    """
    Generates an enterprise-styled .xlsx workbook using openpyxl.
    Applies deep navy headers, alternating row styles, status badges, and column auto-width.
    Returns (excel_bytes, exported_lead_ids, record_count).
    """
    df = get_scoped_dataframe(scope)
    lead_ids = df["id"].tolist() if "id" in df.columns else []

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads Export"

    # Ensure grid lines are visible
    ws.views.sheetView[0].showGridLines = True

    export_cols = [c for c in COLUMN_DISPLAY_NAMES.keys() if c in df.columns]
    display_headers = [COLUMN_DISPLAY_NAMES[c] for c in export_cols]

    # Header styling
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Enterprise Navy
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    wrap_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # Write headers
    for col_idx, header in enumerate(display_headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 28

    if not df.empty:
        # Priority Fills
        high_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")  # Light green
        med_fill = PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid")   # Light yellow
        low_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")   # Light slate
        zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

        for row_idx, (_, row) in enumerate(df[export_cols].iterrows(), 2):
            is_even = (row_idx % 2 == 0)
            ws.row_dimensions[row_idx].height = 22

            for col_idx, col_name in enumerate(export_cols, 1):
                val = row[col_name]
                # Format None/NaN
                if pd.isna(val):
                    val = ""
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name="Calibri", size=10)
                cell.border = thin_border

                # Alignment & Badge Styling
                if col_name in ["id", "lead_score", "is_exported"]:
                    cell.alignment = center_align
                elif col_name == "priority":
                    cell.alignment = center_align
                    val_str = str(val).lower()
                    if "high" in val_str:
                        cell.fill = high_fill
                        cell.font = Font(name="Calibri", size=10, bold=True, color="166534")
                    elif "med" in val_str:
                        cell.fill = med_fill
                        cell.font = Font(name="Calibri", size=10, bold=True, color="854D0E")
                    else:
                        cell.fill = low_fill
                        cell.font = Font(name="Calibri", size=10, color="475569")
                elif col_name in ["summary", "evidence", "requirement", "score_explanation"]:
                    cell.alignment = wrap_align
                else:
                    cell.alignment = left_align
                    if is_even and col_name != "priority":
                        cell.fill = zebra_fill

    # Auto-adjust column widths
    for col_idx, col_name in enumerate(export_cols, 1):
        col_letter = get_column_letter(col_idx)
        max_len = len(display_headers[col_idx - 1])
        if not df.empty:
            for val in df[col_name].dropna().head(100):
                line_len = len(str(val).split("\n")[0])
                if line_len > max_len:
                    max_len = min(line_len, 50)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()

    return excel_bytes, lead_ids, len(df)
