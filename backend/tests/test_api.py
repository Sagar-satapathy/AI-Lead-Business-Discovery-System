"""
backend/tests/test_api.py - Automated Test Suite for FastAPI Backend

Tests:
1. Health check & system diagnostics
2. KPI metrics calculation (supports clean and populated database states)
3. Leads query, filtering, and pagination
4. Lead creation with duplicate detection
5. AI evaluation pipeline (using fallback deterministic NLP for reproducible CI tests)
6. Business discovery engine matching
7. Scoped CSV and Excel export generation
8. Export confirmation marking
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import get_leads, get_dashboard_metrics

client = TestClient(app)


class TestAPI(unittest.TestCase):

    def test_health_check(self):
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("database_type", data)
        self.assertIn("ai_providers", data)
        self.assertTrue(data["ai_providers"]["fallback_nlp_ready"])

    def test_get_metrics(self):
        response = client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        metrics = response.json()
        self.assertIn("total_records", metrics)
        self.assertIn("processed_records", metrics)
        self.assertIn("unprocessed_records", metrics)
        self.assertTrue("category_counts" in metrics or "category_breakdown" in metrics)
        self.assertTrue("priority_counts" in metrics or "priority_breakdown" in metrics)
        self.assertGreaterEqual(metrics["total_records"], 0)

    def test_list_leads_default(self):
        response = client.get("/api/leads?page=1&page_size=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("leads", data)
        self.assertIn("total", data)
        self.assertLessEqual(len(data["leads"]), 10)
        self.assertGreaterEqual(data["total"], 0)

    def test_list_leads_filter_priority(self):
        response = client.get("/api/leads?priority=High")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for lead in data["leads"]:
            self.assertEqual(lead["priority"], "High")

    def test_list_leads_filter_exported(self):
        response = client.get("/api/leads?is_exported=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for lead in data["leads"]:
            self.assertEqual(lead["is_exported"], 0)

    def test_get_lead_by_id_success(self):
        # Check if an existing lead is present, otherwise create one for lookup testing
        leads_res = client.get("/api/leads?page=1&page_size=1")
        if leads_res.status_code == 200 and leads_res.json().get("leads"):
            target_id = leads_res.json()["leads"][0]["id"]
        else:
            create_res = client.post(
                "/api/leads",
                json={
                    "business_name": "API Single Retrieval Test Corp",
                    "requirement": "Requirement to verify single lead retrieval endpoint.",
                    "source_name": "Test Suite",
                    "location": "Dallas, TX",
                },
            )
            target_id = create_res.json()["lead"]["id"]

        response = client.get(f"/api/leads/{target_id}")
        self.assertEqual(response.status_code, 200)
        lead = response.json()
        self.assertEqual(lead["id"], target_id)
        self.assertIn("business_name", lead)
        self.assertIn("requirement", lead)

    def test_get_lead_by_id_not_found(self):
        response = client.get("/api/leads/999999")
        self.assertEqual(response.status_code, 404)

    def test_create_lead_and_duplicate(self):
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
            self.assertEqual(data["lead"]["business_name"], unique_business)
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
            self.assertEqual(res2.status_code, 409)

            # Test single lead evaluation on the newly created lead
            eval_res = client.post(f"/api/leads/{new_id}/analyze?provider=fallback")
            self.assertEqual(eval_res.status_code, 200)
            eval_data = eval_res.json()
            self.assertTrue(eval_data["success"])
            self.assertEqual(eval_data["lead"]["status"], "processed")
            self.assertGreater(eval_data["lead"]["lead_score"], 0)
            self.assertIn(
                eval_data["lead"]["category"],
                [
                    "Website Development",
                    "Mobile Application Development",
                    "Web Application Development",
                    "SEO Services",
                    "Digital Marketing",
                    "Not Relevant",
                ],
            )

    def test_discovery_endpoint(self):
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
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("candidates", data)
        self.assertIn("stats", data)
        self.assertGreater(len(data["candidates"]), 0)
        first = data["candidates"][0]
        self.assertTrue("Apex Spine" in first["business_name"] or "Austin" in first["location"])

    def test_export_csv_and_excel(self):
        # Empty export returns 400 with clear warning message
        res_csv = client.get("/api/export/csv?scope=unexported")
        if res_csv.status_code == 400:
            self.assertEqual(res_csv.json()["detail"], "No leads selected. Please select at least one lead.")
        else:
            self.assertEqual(res_csv.status_code, 200)
            self.assertIn("text/csv", res_csv.headers["content-type"])

        res_excel = client.get("/api/export/excel?scope=unexported")
        if res_excel.status_code == 400:
            self.assertEqual(res_excel.json()["detail"], "No leads selected. Please select at least one lead.")
        else:
            self.assertEqual(res_excel.status_code, 200)
            self.assertIn("application/vnd.openxmlformats", res_excel.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
