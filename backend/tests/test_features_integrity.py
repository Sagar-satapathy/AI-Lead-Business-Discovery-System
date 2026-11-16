"""
backend/tests/test_features_integrity.py - Verifies that search, filters, CSV export, and Excel export continue to work properly.
"""

import sys
import os
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


class TestFeaturesIntegrity(unittest.TestCase):

    def test_search_filter(self):
        """Verifies search by business name returns matching lead."""
        response = client.get("/api/leads?search=GeM&live_only=false&relevance=All&status=All&record_type=All")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data["total"], 1)
        names = [l["business_name"] for l in data["leads"]]
        self.assertTrue(any("GeM" in n for n in names))
        print(f"\n[Search PASS] Found {data['total']} lead(s) for 'GeM': {names}")

    def test_category_filter(self):
        """Verifies category filter for Financial Services."""
        response = client.get("/api/leads?category=Financial+Services&live_only=false&relevance=All&status=All&record_type=All")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        for l in data["leads"]:
            self.assertEqual(l["category"], "Financial Services")
        print(f"[Category Filter PASS] Found {data['total']} leads in 'Financial Services'")

    def test_priority_filter(self):
        """Verifies priority filter for High."""
        response = client.get("/api/leads?priority=High&live_only=false&relevance=All&status=All&record_type=All")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        for l in data["leads"]:
            self.assertEqual(l["priority"], "High")
        print(f"[Priority Filter PASS] Found {data['total']} High Priority leads")

    def test_buying_intent_filter(self):
        """Verifies buying intent filter for Active."""
        response = client.get("/api/leads?buying_intent=Active&live_only=false&relevance=All&status=All&record_type=All")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 3)
        for l in data["leads"]:
            self.assertEqual(l["buying_intent"], "Active")
        print(f"[Buying Intent Filter PASS] Found {data['total']} Active Intent leads")

    def test_csv_export(self):
        """Verifies CSV export for all leads."""
        response = client.get("/api/export/csv?scope=all")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))
        content = response.content
        self.assertGreater(len(content), 0)
        # Check standard headers
        header_line = content.split(b"\n")[0]
        self.assertIn(b"Business Name", header_line)
        print(f"[CSV Export PASS] Generated CSV of {len(content)} bytes with header: {header_line[:60]}...")

    def test_excel_export(self):
        """Verifies Excel export for all leads."""
        response = client.get("/api/export/excel?scope=all")
        self.assertEqual(response.status_code, 200)
        self.assertIn("openxmlformats", response.headers.get("content-type", ""))
        content = response.content
        self.assertGreater(len(content), 0)
        # Check ZIP/XLSX magic signature PK\x03\x04
        self.assertEqual(content[:4], b"PK\x03\x04")
        print(f"[Excel Export PASS] Generated XLSX workbook of {len(content)} bytes with valid ZIP magic header")


if __name__ == "__main__":
    unittest.main()
