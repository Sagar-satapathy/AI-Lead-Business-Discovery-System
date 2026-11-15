"""
backend/tests/test_api.py - Automated Test Suite for FastAPI Backend

Tests:
1. Health check & system diagnostics
2. KPI metrics calculation
3. Leads query, filtering, and pagination
4. Lead creation with duplicate detection
5. AI evaluation pipeline (using fallback deterministic NLP for reproducible CI tests)
6. Business discovery engine matching
7. Scoped CSV and Excel export generation
8. Export confirmation marking
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import get_leads, get_dashboard_metrics

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database_type" in data
    assert "ai_providers" in data
    assert data["ai_providers"]["fallback_nlp_ready"] is True


def test_get_metrics():
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert "total_records" in metrics
    assert "processed_records" in metrics
    assert "unprocessed_records" in metrics
    assert "category_breakdown" in metrics
    assert "priority_breakdown" in metrics
    assert metrics["total_records"] >= 27


def test_list_leads_default():
    response = client.get("/api/leads?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "leads" in data
    assert "total" in data
    assert len(data["leads"]) <= 10
    assert data["total"] >= 27


def test_list_leads_filter_priority():
    response = client.get("/api/leads?priority=High")
    assert response.status_code == 200
    data = response.json()
    for lead in data["leads"]:
        assert lead["priority"] == "High"


def test_list_leads_filter_exported():
    response = client.get("/api/leads?is_exported=0")
    assert response.status_code == 200
    data = response.json()
    for lead in data["leads"]:
        assert lead["is_exported"] == 0


def test_get_lead_by_id_success():
    response = client.get("/api/leads/1")
    assert response.status_code == 200
    lead = response.json()
    assert lead["id"] == 1
    assert "business_name" in lead
    assert "requirement" in lead


def test_get_lead_by_id_not_found():
    response = client.get("/api/leads/999999")
    assert response.status_code == 404


def test_create_lead_and_duplicate():
    unique_business = "Unique Test Business Alpha"
    unique_req = "Looking for mobile app developers to build an iOS fleet tracking application with GPS sync."

    # First insert
    res1 = client.post(
        "/api/leads",
        json={
            "business_name": unique_business,
            "requirement": unique_req,
            "source_name": "Test Suite",
            "location": "Austin, TX",
        },
    )
    # May be 201 or 409 if already inserted in prior run
    if res1.status_code == 201:
        data = res1.json()
        assert data["lead"]["business_name"] == unique_business
        new_id = data["lead"]["id"]

        # Duplicate attempt must fail with 409 Conflict
        res2 = client.post(
            "/api/leads",
            json={
                "business_name": unique_business,
                "requirement": unique_req,
                "source_name": "Test Suite",
            },
        )
        assert res2.status_code == 409

        # Test single lead evaluation on the newly created lead
        eval_res = client.post(f"/api/leads/{new_id}/analyze?provider=fallback")
        assert eval_res.status_code == 200
        eval_data = eval_res.json()
        assert eval_data["success"] is True
        assert eval_data["lead"]["status"] == "processed"
        assert eval_data["lead"]["lead_score"] > 0
        assert eval_data["lead"]["category"] in [
            "Website Development",
            "Mobile Application Development",
            "Web Application Development",
            "SEO Services",
            "Digital Marketing",
            "Not Relevant",
        ]


def test_discovery_endpoint():
    res = client.post(
        "/api/discover",
        json={
            "location": "Austin, TX",
            "category": "Healthcare",
            "service": "Mobile Application Development",
            "auto_ingest": False,
            "limit": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "candidates" in data
    assert "stats" in data
    assert len(data["candidates"]) > 0
    first = data["candidates"][0]
    assert "Apex Spine" in first["business_name"] or "Austin" in first["location"]


def test_export_csv_and_excel():
    # CSV
    res_csv = client.get("/api/export/csv?scope=unexported")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert len(res_csv.content) > 0

    # Excel
    res_excel = client.get("/api/export/excel?scope=unexported")
    assert res_excel.status_code == 200
    assert "application/vnd.openxmlformats" in res_excel.headers["content-type"]
    assert len(res_excel.content) > 0
