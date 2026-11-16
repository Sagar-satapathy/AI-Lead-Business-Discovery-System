"""
backend/main.py - Enterprise FastAPI Application

REST API providing:
- Health check & System Diagnostics (/api/health)
- Aggregated Business Intelligence & KPI Metrics (/api/metrics)
- Paginated & Filtered Lead Queries (/api/leads)
- Single & Batch Lead AI Analysis with Verbatim Evidence (/api/leads/analyze)
- Multi-Source Commercial Business Discovery (/api/discover)
- CSV File Upload & Schema Ingestion Pipeline (/api/leads/upload)
- Scoped CSV and Styled Excel Export with Confirmation (/api/export)
"""

from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
import os
import datetime
import io
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.db import (
    init_database,
    get_leads,
    get_lead_by_id,
    insert_lead,
    mark_leads_as_exported,
    get_dashboard_metrics,
    is_postgres,
    update_source_verification,
    update_lead_analysis,
    get_lead_by_name_and_req,
    save_discovery_staging_batch,
    get_discovery_staging_batch,
    save_staged_batch_to_pipeline,
    clear_discovery_staging_batch,
)
from backend.services.ai_service import (
    process_and_save_lead,
    evaluate_lead,
    ALLOWED_CATEGORIES,
    ALLOWED_BUYING_INTENT,
    ALLOWED_RELEVANCE,
)
from backend.services.discovery_service import discover_leads
from backend.services.source_verifier import verify_source_url
from backend.services.serper_provider import SerperProvider
from backend.services.provider_manager import get_all_providers_status
from backend.services.export_service import generate_csv_bytes, generate_excel_bytes, EXPORT_SCOPES
import data_processor


# Initialize FastAPI App
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise REST API for AI Lead Discovery, Intent Classification, and Procurement Scoring.",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Request/Response Pydantic Schemas
# ---------------------------------------------------------------------------

class LeadCreateRequest(BaseModel):
    business_name: str = Field(..., min_length=1, description="Company or business name")
    requirement: str = Field(..., min_length=5, description="Full description of digital requirement or RFP")
    source_name: str = Field("Manual Ingestion", description="Data source or platform")
    source_url: str = Field("", description="Source reference link")
    location: str = Field("", description="Geographic location or market")
    date_found: Optional[str] = Field(None, description="Date record was found (YYYY-MM-DD)")


class AnalyzeBatchRequest(BaseModel):
    lead_ids: Optional[List[int]] = Field(None, description="Specific lead IDs to analyze. If empty, evaluates unprocessed.")
    provider: Optional[str] = Field(None, description="Preferred AI provider: 'openai', 'gemini', 'fallback', or 'auto'")
    all_unprocessed: bool = Field(True, description="Whether to analyze all unprocessed records if lead_ids is empty")


class DiscoveryRequest(BaseModel):
    location: str = Field("", description="Target geographic market (e.g., 'Austin, TX', 'London')")
    category: str = Field("", description="Business category/industry (e.g., 'Healthcare', 'Legal')")
    service: str = Field("", description="Digital service sought (e.g., 'Mobile App', 'SEO')")
    auto_ingest: bool = Field(True, description="Automatically ingest discovered candidates into the database")
    auto_analyze: bool = Field(False, description="Automatically trigger AI analysis on newly ingested records")
    limit: int = Field(10, ge=1, le=50, description="Maximum candidates to return")


class SaveBatchRequest(BaseModel):
    candidates: Optional[List[Dict[str, Any]]] = Field(None, description="Optional candidates list to save; if None, saves from staging table.")


class ExportConfirmRequest(BaseModel):
    lead_ids: List[int] = Field(..., min_items=1, description="List of lead IDs to mark as exported")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["System"])
def health_check():
    """Returns application health, database engine, available AI providers, and discovery mode."""
    if (settings.IS_PRODUCTION or settings.IS_VERCEL) and not is_postgres():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "app_name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "database_type": "None",
                "error": "DATABASE_URL environment variable is mandatory in production / on Vercel. SQLite fallback is disabled.",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )
    metrics = get_dashboard_metrics()
    disc_status = get_all_providers_status()
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database_type": "PostgreSQL" if is_postgres() else "SQLite",
        "ai_providers": {
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "gemini_configured": bool(settings.GEMINI_API_KEY),
            "fallback_nlp_ready": True,
            "active_preferred": settings.AI_PROVIDER,
        },
        "discovery": {
            "live_search_configured": disc_status["live_search_configured"],
            "provider": disc_status["active_provider"],
            "active_provider": disc_status["active_provider"],
            "configured_preference": disc_status["configured_preference"],
            "operational": disc_status["operational"],
            "live_search_executed": disc_status["live_search_executed"],
            "mode": disc_status["mode"],
            "tavily_configured": disc_status["providers"]["tavily"]["configured"],
            "serper_configured": disc_status["providers"]["serper"]["configured"],
            "providers": disc_status["providers"],
        },
        "stats": {
            "total_records": metrics.get("total_records", 0),
            "processed_records": metrics.get("processed_records", 0),
            "unprocessed_records": metrics.get("unprocessed_records", 0),
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/api/metrics", tags=["Analytics"])
def get_metrics(response: Response):
    """Returns aggregated KPI summary metrics and category/priority breakdowns."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    metrics = get_dashboard_metrics()
    return metrics


@app.get("/api/leads", tags=["Leads"])
def list_leads(
    search: Optional[str] = Query(None, description="Search term in name, requirement, or summary"),
    category: Optional[str] = Query(None, description="Filter by service category"),
    priority: Optional[str] = Query(None, description="Filter by priority: High, Medium, Low"),
    buying_intent: Optional[str] = Query(None, description="Filter by buying intent: Active, Potential, Unclear"),
    relevance: Optional[str] = Query(None, description="Filter by relevance: Relevant, Not Relevant"),
    status: Optional[str] = Query(None, description="Filter by status: processed, unprocessed, failed"),
    is_exported: Optional[str] = Query(None, description="Filter by export status: 0, 1, 'Exported', 'Not Exported'"),
    record_type: Optional[str] = Query(None, description="Filter by record type: demo, uploaded, discovered, sample"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status: verified, unverified, demo"),
    source_page_type: Optional[str] = Query(None, description="Filter by verified source page type: buyer_procurement, seller_agency, portfolio, directory, unknown"),
    is_live_discovery: Optional[int] = Query(None, description="Filter by live discovery flag: 1 or 0"),
    live_only: bool = Query(False, description="Filter strictly for genuine live-discovered, processed, relevant leads"),
    order_by: str = Query("id_asc", description="Sort order: id_asc, id_desc, score_desc, score_asc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Records per page"),
):
    """Retrieves paginated, filtered leads with total count and paging metadata."""
    p = int(getattr(page, "default", page)) if hasattr(page, "default") else int(page)
    ps = int(getattr(page_size, "default", page_size)) if hasattr(page_size, "default") else int(page_size)
    skip = (p - 1) * ps

    parsed_is_exported: Optional[int] = None
    if is_exported is not None and not hasattr(is_exported, "default"):
        raw_exp = str(is_exported).strip().lower()
        if raw_exp in ("1", "exported", "true"):
            parsed_is_exported = 1
        elif raw_exp in ("0", "not exported", "unexported", "false"):
            parsed_is_exported = 0

    leads, total = get_leads(
        search=None if hasattr(search, "default") else search,
        category=None if hasattr(category, "default") else category,
        priority=None if hasattr(priority, "default") else priority,
        buying_intent=None if hasattr(buying_intent, "default") else buying_intent,
        relevance=None if hasattr(relevance, "default") else relevance,
        status=None if hasattr(status, "default") else status,
        is_exported=parsed_is_exported,
        record_type=None if hasattr(record_type, "default") else record_type,
        verification_status=None if hasattr(verification_status, "default") else verification_status,
        source_page_type=None if hasattr(source_page_type, "default") else source_page_type,
        is_live_discovery=None if hasattr(is_live_discovery, "default") else is_live_discovery,
        live_only=bool(getattr(live_only, "default", live_only)) if hasattr(live_only, "default") else bool(live_only),
        order_by="id_asc" if hasattr(order_by, "default") else order_by,
        skip=skip,
        limit=ps,
    )
    total_pages = (total + ps - 1) // ps if total > 0 else 1

    return {
        "leads": leads,
        "total": total,
        "page": p,
        "page_size": ps,
        "total_pages": total_pages,
    }


@app.get("/api/leads/{lead_id}", tags=["Leads"])
def get_lead(lead_id: int):
    """Retrieves full details, AI classification, and scoring breakdown for a single lead."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found.")
    return lead


@app.post("/api/leads", tags=["Leads"], status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreateRequest):
    """Manually ingests a single business lead with duplicate prevention."""
    today_str = payload.date_found or datetime.date.today().strftime("%Y-%m-%d")
    success, new_id, msg = insert_lead(
        business_name=payload.business_name,
        requirement=payload.requirement,
        source_name=payload.source_name,
        source_url=payload.source_url,
        location=payload.location,
        date_found=today_str,
        status="unprocessed",
    )
    if not success:
        raise HTTPException(status_code=409, detail=msg)

    created = get_lead_by_id(new_id)
    return {
        "message": msg,
        "lead": created,
    }


@app.post("/api/leads/{lead_id}/analyze", tags=["AI & Evaluation"])
def analyze_single_lead(
    lead_id: int,
    provider: Optional[str] = Query(None, description="Specific AI provider to use"),
):
    """Triggers AI evaluation and deterministic 5-factor scoring for a single lead."""
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found.")

    success, msg, result = process_and_save_lead(
        lead_id=lead_id,
        requirement=lead["requirement"],
        business_name=lead["business_name"],
        provider=provider,
    )

    updated_lead = get_lead_by_id(lead_id)
    if not success:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": msg,
                "lead": updated_lead,
            },
        )

    return {
        "success": True,
        "message": msg,
        "lead": updated_lead,
    }


@app.post("/api/leads/{lead_id}/verify-source", tags=["Verification"])
async def verify_lead_source(lead_id: int):
    """
    On-demand re-verification of the original source URL for a lead.
    Re-fetches the target webpage, executes SSRF and DNS security checks,
    analyzes page DOM for genuine buyer procurement vs seller agency/portfolio signals,
    updates database verification metadata, and returns the verification result.
    """
    lead = get_lead_by_id(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead with ID {lead_id} not found.")

    source_url = (lead.get("source_url") or "").strip()
    if not source_url:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Lead does not have a source URL to verify.",
                "lead": lead,
            },
        )

    try:
        ver_res = await verify_source_url(source_url, timeout_seconds=5.0)

        notes = ver_res.get("notes") or ""
        evidence_snip = ver_res.get("evidence_snippet") or ""
        fetch_status = ver_res.get("fetch_status") or "unknown"
        page_type = ver_res.get("page_type") or "unknown"
        now_ts = ver_res.get("verified_at") or datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Update in database without overwriting existing verification_status unless confirmed
        update_source_verification(
            lead_id=lead_id,
            fetch_status=fetch_status,
            page_type=page_type,
            verified_at=now_ts,
            evidence_snippet=evidence_snip,
            verification_notes=notes if notes else None,
        )

        updated_lead = get_lead_by_id(lead_id)
        return {
            "success": True,
            "message": f"Source page verified: {notes}",
            "verification": ver_res,
            "lead": updated_lead,
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Source verification encountered an error: {str(e)}",
                "lead": lead,
            },
        )


@app.post("/api/leads/analyze", tags=["AI & Evaluation"])
def analyze_batch(payload: AnalyzeBatchRequest):
    """
    Evaluates multiple leads in batch.
    Processes specified IDs or all currently unprocessed leads.
    """
    targets = []
    if payload.lead_ids:
        for lid in payload.lead_ids:
            l = get_lead_by_id(lid)
            if l:
                targets.append(l)
    elif payload.all_unprocessed:
        unprocessed_leads, _ = get_leads(status="unprocessed", limit=100)
        targets = unprocessed_leads

    if not targets:
        return {
            "message": "No eligible leads found for batch evaluation.",
            "processed_count": 0,
            "failed_count": 0,
            "results": [],
        }

    results = []
    success_count = 0
    fail_count = 0

    for item in targets:
        ok, msg, res = process_and_save_lead(
            lead_id=item["id"],
            requirement=item["requirement"],
            business_name=item["business_name"],
            provider=payload.provider,
        )
        if ok:
            success_count += 1
            results.append({"id": item["id"], "status": "processed", "score": res["scoring"]["total_score"]})
        else:
            fail_count += 1
            results.append({"id": item["id"], "status": "failed", "error": msg})

    return {
        "message": f"Batch completed: {success_count} evaluated successfully, {fail_count} failed.",
        "processed_count": success_count,
        "failed_count": fail_count,
        "results": results,
    }


@app.post("/api/discover", tags=["Discovery"])
def execute_discovery(payload: DiscoveryRequest):
    """
    Discovers business leads matching location, category, and requested digital services.
    Automatically evaluates every discovered candidate with AI analysis and 5-factor scoring,
    checks duplicate status against the pipeline, and stages results in SQLite.
    """
    candidates, stats = discover_leads(
        location=payload.location,
        category=payload.category,
        service=payload.service,
        auto_ingest=payload.auto_ingest,
        limit=payload.limit,
    )

    # Automatically analyze and score every discovered candidate
    analyzed_count = 0
    for cand in candidates:
        ok, ai_res, score_res, err = evaluate_lead(
            requirement=cand.get("requirement", ""),
            business_name=cand.get("business_name", ""),
        )
        if ok:
            cand["buying_intent"] = ai_res.get("buying_intent", "Unclear")
            cand["relevance"] = ai_res.get("business_relevance", "Relevant")
            cand["summary"] = ai_res.get("summary", "")
            cand["evidence"] = ai_res.get("evidence", "")
            cand["lead_score"] = score_res.get("total_score", 0)
            cand["priority"] = score_res.get("priority", "Low")
            cand["score_breakdown"] = score_res.get("breakdown", {})
            cand["score_explanation"] = score_res.get("explanation", {})
            cand["analysis_status"] = "analyzed"
            analyzed_count += 1
            if payload.auto_ingest and cand.get("id"):
                update_lead_analysis(cand["id"], ai_res, score_res)
        else:
            cand["analysis_status"] = "failed"
            cand["analysis_error"] = err

        # Check duplicate status against existing pipeline in leads table
        existing = get_lead_by_name_and_req(cand.get("business_name", ""), cand.get("requirement", ""))
        if existing:
            cand["existing_lead_id"] = existing["id"]
            cand["id"] = existing["id"]
            cand["ingest_status"] = "already_exists"
        else:
            cand["existing_lead_id"] = None
            if not payload.auto_ingest:
                cand["id"] = None
                cand["ingest_status"] = "unprocessed"

    # Persist the current discovery batch to SQLite discovery_staging table
    # Only stage genuine live discoveries, never demo or static benchmark candidates
    live_to_stage = [
        c for c in candidates
        if c.get("is_live_discovery") and c.get("record_type") not in ("demo", "sample") and c.get("verification_status") != "demo"
    ]
    save_discovery_staging_batch(live_to_stage)

    stats["auto_analyzed"] = analyzed_count
    stats["already_in_pipeline"] = sum(1 for c in candidates if c.get("existing_lead_id"))
    stats["new_opportunities"] = sum(1 for c in candidates if not c.get("existing_lead_id"))
    if not payload.auto_ingest:
        stats["newly_ingested"] = 0
        stats["duplicates_skipped"] = stats["already_in_pipeline"]

    return {
        "candidates": candidates,
        "stats": stats,
    }


@app.get("/api/discovery/current-batch", tags=["Discovery"])
def get_current_discovery_batch():
    """
    Retrieves the currently staged discovery batch from SQLite.
    Survives page reloads and tab navigation.
    Only returns genuine live discoveries, never static demonstration benchmarks.
    """
    candidates = get_discovery_staging_batch()
    live_candidates = [
        c for c in candidates
        if c.get("is_live_discovery") and c.get("record_type") not in ("demo", "sample") and c.get("verification_status") != "demo"
    ]
    return {
        "candidates": live_candidates,
        "count": len(live_candidates),
    }


@app.post("/api/discovery/save-batch", tags=["Discovery"])
def save_discovery_batch(payload: Optional[SaveBatchRequest] = None):
    """
    Persists newly discovered candidates from the current batch into the main leads pipeline (leads table)
    with processed status, AI evaluation, and 5-factor scores.
    Skips duplicates and clears the staging table.
    """
    candidates = payload.candidates if payload else None
    saved_count, dup_count, msg = save_staged_batch_to_pipeline(candidates)
    return {
        "success": True,
        "saved_count": saved_count,
        "duplicates_skipped": dup_count,
        "message": msg,
    }


@app.post("/api/discovery/clear-batch", tags=["Discovery"])
def clear_discovery_batch():
    """Clears the discovery staging batch."""
    clear_discovery_staging_batch()
    return {
        "success": True,
        "message": "Discovery batch cleared successfully.",
    }


@app.post("/api/leads/upload", tags=["Data Ingestion"])
def upload_csv(file: UploadFile = File(...)):
    """
    Validates and ingests leads from an uploaded CSV file.
    Performs schema validation, duplicate detection, and whitespace sanitization.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    content = file.file.read()
    bio = io.BytesIO(content)

    is_valid, df, err_msg, stats = data_processor.load_and_validate_csv(bio)
    if not is_valid or df is None:
        raise HTTPException(status_code=422, detail=f"CSV validation failed: {err_msg}")

    inserted_count = 0
    duplicate_count = 0

    for _, row in df.iterrows():
        ok, _, _ = insert_lead(
            business_name=str(row["business_name"]),
            requirement=str(row["requirement"]),
            source_name=str(row.get("source_name", "CSV Upload")),
            source_url=str(row.get("source_url", "")),
            location=str(row.get("location", "")),
            date_found=str(row.get("date_found", datetime.date.today().strftime("%Y-%m-%d"))),
            status="unprocessed",
            record_type="uploaded",
            verification_status="unverified",
            verification_notes="Ingested from user CSV upload",
        )
        if ok:
            inserted_count += 1
        else:
            duplicate_count += 1

    return {
        "message": f"Successfully ingested {inserted_count} new leads ({duplicate_count} duplicates skipped).",
        "validation_stats": stats,
        "inserted_count": inserted_count,
        "duplicates_skipped": duplicate_count,
    }


@app.get("/api/export/csv", tags=["Export"])
def export_csv(
    scope: str = Query("unexported", description="Export scope: unexported, processed, high_medium, all"),
    lead_ids: Optional[str] = Query(None, description="Comma-separated lead IDs to export (optional)"),
):
    """Generates a downloadable CSV export file for the selected scope or specific lead IDs."""
    scope_str = str(getattr(scope, "default", scope)) if hasattr(scope, "default") else str(scope)

    parsed_ids: Optional[List[int]] = None
    if lead_ids is not None:
        raw_ids = [x.strip() for x in lead_ids.split(",") if x.strip()]
        if not raw_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No leads selected. Please select at least one lead.",
            )
        try:
            parsed_ids = [int(x) for x in raw_ids]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid lead IDs provided. All IDs must be integers.",
            )

    csv_bytes, exported_lead_ids, count = generate_csv_bytes(scope_str, lead_ids=parsed_ids)

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leads selected. Please select at least one lead.",
        )

    filename = f"leads_export_{scope_str}_{datetime.date.today().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Count": str(count),
            "X-Export-Ids": ",".join(str(i) for i in exported_lead_ids[:100]),
        },
    )


@app.get("/api/export/excel", tags=["Export"])
def export_excel(
    scope: str = Query("unexported", description="Export scope: unexported, processed, high_medium, all"),
    lead_ids: Optional[str] = Query(None, description="Comma-separated lead IDs to export (optional)"),
):
    """Generates a styled, downloadable Excel (.xlsx) workbook for the selected scope or specific lead IDs."""
    scope_str = str(getattr(scope, "default", scope)) if hasattr(scope, "default") else str(scope)

    parsed_ids: Optional[List[int]] = None
    if lead_ids is not None:
        raw_ids = [x.strip() for x in lead_ids.split(",") if x.strip()]
        if not raw_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No leads selected. Please select at least one lead.",
            )
        try:
            parsed_ids = [int(x) for x in raw_ids]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid lead IDs provided. All IDs must be integers.",
            )

    excel_bytes, exported_lead_ids, count = generate_excel_bytes(scope_str, lead_ids=parsed_ids)

    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No leads selected. Please select at least one lead.",
        )

    filename = f"leads_export_{scope_str}_{datetime.date.today().strftime('%Y%m%d')}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Count": str(count),
            "X-Export-Ids": ",".join(str(i) for i in exported_lead_ids[:100]),
        },
    )


@app.post("/api/export/confirm", tags=["Export"])
def confirm_export(payload: ExportConfirmRequest):
    """
    Marks exported lead records with is_exported = 1 and records the export timestamp.
    """
    updated_count = mark_leads_as_exported(payload.lead_ids)
    return {
        "success": True,
        "message": f"Successfully marked {updated_count} lead(s) as exported.",
        "exported_count": updated_count,
    }


# Mount compiled React frontend if present
from fastapi.staticfiles import StaticFiles
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

if os.path.exists(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
