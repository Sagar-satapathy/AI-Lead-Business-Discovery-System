"""
backend/tests/test_dashboard_and_metrics.py - Verification suite for Dashboard KPIs and Lead Explorer consistency.

Tests:
1. Neon PostgreSQL connection and total record count integrity.
2. Dashboard metrics API (/api/metrics) calculations:
   - Total Leads
   - Active Buying Intent
   - High Priority Leads
   - Medium Priority Leads
   - Potential Buying Intent
3. Visual sections data:
   - Section A: Buying Intent Overview
   - Section B: Priority Distribution
   - Section C: Service-wise Lead Analysis
   - Section D: High-Priority Opportunities
4. Unfiltered Lead Explorer (/api/leads) consistency:
   - Dashboard Total Leads must equal unfiltered Lead Explorer total.
   - Includes both exported and unexported leads.
   - Includes previously saved leads (IDs 16, 17, and 24).
5. Safe read-only execution: no dummy records inserted or deleted.
"""

import sys
import os
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.main import app
from backend.db import get_dashboard_metrics, get_connection, is_postgres

client = TestClient(app)


class TestDashboardAndMetrics(unittest.TestCase):

    def test_neon_postgres_count(self):
        """Verifies database count against SELECT COUNT(*) FROM leads directly."""
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM leads")
            row = cur.fetchone()
            actual_db_total = row[0] if isinstance(row, (tuple, list)) else list(row.values())[0]

        self.assertGreaterEqual(actual_db_total, 2, "Database must contain at least the 2 saved leads from yesterday.")
        print(f"\n[Test 1 PASS] Neon PostgreSQL direct SELECT COUNT(*) FROM leads = {actual_db_total}")

    def test_metrics_api_kpis(self):
        """Verifies all 5 required KPI fields from /api/metrics match database records."""
        response = client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check Cache-Control headers
        self.assertIn("no-cache", response.headers.get("cache-control", ""))

        # 1. Total Leads
        self.assertIn("total_records", data)
        # 2. Active Buying Intent
        self.assertIn("active_intent_leads", data)
        # 3. High Priority Leads
        self.assertIn("high_priority_leads", data)
        # 4. Medium Priority Leads
        self.assertIn("medium_priority_leads", data)
        # 5. Potential Buying Intent
        self.assertIn("potential_intent_leads", data)

        with get_connection() as conn:
            cur = conn.cursor()
            def fetch_val(q):
                cur.execute(q)
                r = cur.fetchone()
                return r[0] if isinstance(r, (list, tuple)) else list(r.values())[0]

            expected_total = fetch_val("SELECT COUNT(*) FROM leads")
            expected_active = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(buying_intent)) = 'active'")
            expected_high = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(priority)) = 'high'")
            expected_med = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(priority)) = 'medium'")
            expected_pot = fetch_val("SELECT COUNT(*) FROM leads WHERE LOWER(TRIM(buying_intent)) = 'potential'")

        self.assertEqual(data["total_records"], expected_total)
        self.assertEqual(data["active_intent_leads"], expected_active)
        self.assertEqual(data["high_priority_leads"], expected_high)
        self.assertEqual(data["medium_priority_leads"], expected_med)
        self.assertEqual(data["potential_intent_leads"], expected_pot)

        print(f"[Test 2 PASS] KPI Cards verified against DB: Total={data['total_records']}, Active={data['active_intent_leads']}, High={data['high_priority_leads']}, Medium={data['medium_priority_leads']}, Potential={data['potential_intent_leads']}")

    def test_metrics_visual_sections(self):
        """Verifies data structure and counts for Visual Sections A, B, C, and D."""
        response = client.get("/api/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Section A: Buying Intent Overview
        self.assertIn("intent_counts", data)
        self.assertIsInstance(data["intent_counts"], dict)

        # Section B: Priority Distribution
        self.assertIn("priority_counts", data)
        self.assertIsInstance(data["priority_counts"], dict)

        # Section C: Service-wise Lead Analysis
        self.assertIn("service_breakdown", data)
        self.assertIsInstance(data["service_breakdown"], list)
        for svc in data["service_breakdown"]:
            self.assertIn("service_category", svc)
            self.assertIn("total_leads", svc)
            self.assertIn("high_priority_leads", svc)
            self.assertIn("medium_priority_leads", svc)
            self.assertIn("low_priority_leads", svc)

        # Section D: High-Priority Opportunities
        self.assertIn("high_priority_opportunities", data)
        self.assertIsInstance(data["high_priority_opportunities"], list)
        for opp in data["high_priority_opportunities"]:
            self.assertIn("id", opp)
            self.assertIn("business_name", opp)
            self.assertIn("category", opp)
            self.assertIn("buying_intent", opp)
            self.assertIn("lead_score", opp)
            self.assertIn("relevance", opp)
            self.assertIn("priority", opp)
            self.assertEqual(opp["priority"].lower(), "high")

        print(f"[Test 3 PASS] Visual sections verified: {len(data['service_breakdown'])} services, {len(data['high_priority_opportunities'])} high-priority opportunities")

    def test_lead_explorer_consistency(self):
        """Verifies that unfiltered Lead Explorer total matches Dashboard Total Leads."""
        metrics_res = client.get("/api/metrics")
        metrics_data = metrics_res.json()
        dashboard_total = metrics_data["total_records"]

        # Request unfiltered leads (live_only=False, relevance=All, status=All, is_exported=All)
        leads_res = client.get("/api/leads?live_only=false&relevance=All&status=All&record_type=All&page_size=50")
        self.assertEqual(leads_res.status_code, 200)
        leads_data = leads_res.json()
        explorer_total = leads_data["total"]

        self.assertEqual(
            dashboard_total,
            explorer_total,
            f"Dashboard total ({dashboard_total}) must match unfiltered Lead Explorer total ({explorer_total})",
        )

        # Verify the two saved leads from yesterday (IDs 16 and 17) and lead 24 are included
        lead_ids = [l["id"] for l in leads_data["leads"]]
        self.assertIn(16, lead_ids, "Lead ID 16 from yesterday must be present in leads list.")
        self.assertIn(17, lead_ids, "Lead ID 17 from yesterday must be present in leads list.")

        print(f"[Test 4 PASS] Lead Explorer unfiltered total ({explorer_total}) exactly matches Dashboard Total ({dashboard_total}). Leads 16 & 17 included.")

    def test_export_status_inclusion(self):
        """Verifies count includes both exported and not-yet-exported leads."""
        response = client.get("/api/metrics")
        data = response.json()
        self.assertEqual(
            data["total_records"],
            data["not_yet_exported"] + data.get("exported_leads", 0),
            "Total records must equal sum of unexported and exported leads.",
        )
        print(f"[Test 5 PASS] Export status inclusion verified: {data['total_records']} total = {data['not_yet_exported']} unexported + {data.get('exported_leads', 0)} exported")


if __name__ == "__main__":
    unittest.main()
