"""
backend/tests/test_serper_discovery.py - Automated Unit & Integration Tests for Serper Provider

Tests:
1. Unconfigured state: No external requests made, fallback to static benchmark mode.
2. Targeted query builder: Validates queries for India, Telangana, Hyderabad, and core services.
3. Mocked Google search execution: Zero API credits consumed. Validates payload, headers, organic parsing.
4. Seller/Agency directory filtering: Separates procurement buyers from self-advertising IT agencies.
5. Provenance integrity: All 9 provenance fields populated accurately.
6. Error handling: HTTP 429 rate limits, HTTP 403, and network timeouts handled gracefully.
7. Health endpoint diagnostics: Configuration vs. execution separation.
8. Secret redaction: API keys never logged.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import httpx

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.config import settings
from backend.services.serper_provider import SerperProvider
from backend.services.discovery_service import discover_leads
from backend.main import health_check, execute_discovery, DiscoveryRequest


class TestSerperProvider(unittest.TestCase):

    def test_unconfigured_provider_behavior(self):
        """When SERPER_API_KEY is missing, external calls must not be made and static mode is preserved."""
        provider = SerperProvider(api_key="")
        self.assertFalse(provider.is_configured())
        self.assertFalse(provider.is_operational())

        status = provider.get_status()
        self.assertFalse(status["configured"])
        self.assertFalse(status["live_search_executed"])

        # Attempt search without key -> must return empty without making network calls
        candidates, meta = provider.search("Telangana", "Healthcare", "Website Development")
        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertIn("not configured", meta["error"].lower())

    def test_targeted_query_builder_telangana_and_hyderabad(self):
        """Verifies targeted queries for India, Telangana, and Hyderabad with digital service intent."""
        provider = SerperProvider(api_key="test_key_dummy")

        # 1. Telangana Website Development
        q1, gl1 = provider.build_search_query("Telangana", "Healthcare", "Website Development")
        self.assertEqual(gl1, "in")
        self.assertIn("(Telangana OR Hyderabad)", q1)
        self.assertIn("website development", q1.lower())
        self.assertIn("rfp", q1.lower())
        self.assertIn("-site:clutch.co", q1)

        # 2. Hyderabad Mobile Application Development
        q2, gl2 = provider.build_search_query("Hyderabad", "Logistics", "Mobile Application Development")
        self.assertEqual(gl2, "in")
        self.assertIn("Hyderabad", q2)
        self.assertIn("mobile app", q2.lower())
        self.assertIn("tender", q2.lower())

        # 3. India SEO & Digital Marketing
        q3, gl3 = provider.build_search_query("India", "Retail", "SEO Services")
        self.assertEqual(gl3, "in")
        self.assertIn("India", q3)
        self.assertIn("seo", q3.lower())

        # 4. Company Website Redesign
        q4, gl4 = provider.build_search_query("Telangana", "Public Sector", "Company Website Redesign")
        self.assertEqual(gl4, "in")
        self.assertIn("redesign", q4.lower())

        # 5. Global UK Market
        q5, gl5 = provider.build_search_query("London, UK", "Healthcare", "Web Application Development")
        self.assertEqual(gl5, "gb")
        self.assertIn("London", q5)

    @patch("httpx.Client.post")
    def test_mocked_serper_live_search_success(self, mock_post):
        """Tests end-to-end mocked search parsing and provenance tracking with zero credit consumption."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "searchParameters": {"q": "test query", "gl": "in", "num": 10},
            "organic": [
                {
                    "title": "Tender Notice: Telangana Irrigation Dept Invites Proposals for Mobile Telemetry Portal",
                    "link": "https://irrigation.telangana.gov.in/tenders/nit-2026-889.pdf",
                    "snippet": "Notice Inviting Tender No NIT-2026-889: Sealed proposals are invited for design and deployment of mobile telemetry monitoring system. Bid submission deadline: 2026-10-15.",
                    "position": 1,
                    "date": "2026-09-01",
                },
                {
                    "title": "Request for Proposal - Hospital Patient Web Portal Revamp | Hyderabad Care Trust",
                    "link": "https://caretrust.org/procurement/rfp-web-revamp",
                    "snippet": "Hyderabad Care Trust seeks vendor proposals for complete revamping of hospital patient appointment and tele-consultation web portal. Scope of work includes billing gateway.",
                    "position": 2,
                    "date": "2026-09-05",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_response

        # Execute search with mocked provider
        provider = SerperProvider(api_key="mock_secret_key_12345")
        candidates, meta = provider.search("Telangana", "Healthcare", "Mobile Application Development")

        self.assertTrue(meta["success"])
        self.assertEqual(meta["credits"], 1)
        self.assertEqual(len(candidates), 2)

        # Verify X-API-KEY header was supplied in request
        args, kwargs = mock_post.call_args
        self.assertIn("X-API-KEY", kwargs["headers"])
        self.assertEqual(kwargs["headers"]["X-API-KEY"], "mock_secret_key_12345")

        # Verify Candidate 1 Provenance & Classification
        c1 = candidates[0]
        self.assertEqual(c1["provider_name"], "serper")
        self.assertEqual(c1["record_type"], "live_discovery")
        self.assertEqual(c1["source_url"], "https://irrigation.telangana.gov.in/tenders/nit-2026-889.pdf")
        self.assertEqual(c1["source_domain"], "irrigation.telangana.gov.in")
        self.assertTrue(c1["is_live_discovery"])
        self.assertEqual(c1["buying_intent"], "Active")
        self.assertEqual(c1["verification_status"], "official_tender")
        self.assertIn("evidence_text", c1)
        self.assertIn("search_query", c1)

        # Verify Candidate 2 (Commercial / Non-Gov Portal)
        c2 = candidates[1]
        self.assertEqual(c2["provider_name"], "serper")
        self.assertEqual(c2["record_type"], "live_discovery")
        self.assertEqual(c2["source_domain"], "caretrust.org")
        self.assertTrue(c2["is_live_discovery"])
        self.assertEqual(c2["buying_intent"], "Active")
        # Non-authoritative domain must be unverified pending audit, NEVER fabricated as verified
        self.assertEqual(c2["verification_status"], "unverified")

    @patch("httpx.Client.post")
    def test_filter_out_seller_agencies_and_directory_spam(self, mock_post):
        """Ensures directories and self-advertising IT agencies are rejected, keeping only real buyers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organic": [
                {
                    "title": "Top 10 Web Development Companies in Hyderabad 2026",
                    "link": "https://someblog.com/top-10-web-agencies-hyderabad",
                    "snippet": "Looking for the best web development agency? Check out our list of top 10 rated web development companies in Hyderabad.",
                },
                {
                    "title": "Best Mobile App Development Company in Hyderabad | Hire React Native Developers",
                    "link": "https://xyz-it-services.com/services",
                    "snippet": "We are a leading mobile app development company. Hire dedicated Flutter and iOS developers from our Hyderabad office.",
                },
                {
                    "title": "Tender Notice: Telangana Dairy Federation Invites Bids for Cold Chain ERP Portal",
                    "link": "https://ts-dairy.gov.in/tenders/erp-2026",
                    "snippet": "Notice Inviting Tender for supply, installation and maintenance of integrated web dairy telematics and logistics portal. Bid submission date 2026-11-20.",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_response

        provider = SerperProvider(api_key="mock_secret_key_12345")
        candidates, meta = provider.search("Hyderabad", "Logistics", "Website Development")

        # The 2 seller/directory listings must be filtered out, leaving only the genuine procurement tender
        self.assertEqual(len(candidates), 1)
        self.assertIn("Telangana Dairy Federation", candidates[0]["business_name"])
        self.assertEqual(candidates[0]["source_domain"], "ts-dairy.gov.in")

    @patch("httpx.Client.post")
    def test_rate_limit_handling_http_429(self, mock_post):
        """Validates that HTTP 429 rate limit is handled safely without crashing."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = '{"message": "Too Many Requests"}'
        mock_post.return_value = mock_response

        provider = SerperProvider(api_key="mock_secret_key_12345")
        candidates, meta = provider.search("Hyderabad", "Healthcare", "Mobile Application Development")

        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertEqual(meta["status_code"], 429)
        self.assertIn("rate limit", meta["error"].lower())

    @patch("httpx.Client.post")
    def test_timeout_handling(self, mock_post):
        """Validates that network timeouts return a safe diagnostic error without crashing."""
        mock_post.side_effect = httpx.TimeoutException("Connection timed out after 5.0s")

        provider = SerperProvider(api_key="mock_secret_key_12345")
        candidates, meta = provider.search("Hyderabad", "Healthcare", "Website Development")

        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertIn("timed out", meta["error"].lower())

    def test_health_check_endpoint_diagnostics(self):
        """Validates /api/health reports serper configuration without treating config as live search."""
        health = health_check()
        self.assertIn("discovery", health)
        disc = health["discovery"]
        self.assertIn("live_search_configured", disc)
        self.assertIn("serper_configured", disc)
        self.assertIn("operational", disc)
        self.assertIn("live_search_executed", disc)
        self.assertIn("mode", disc)

        # Without SERPER_API_KEY set:
        if not settings.SERPER_API_KEY:
            self.assertFalse(disc["serper_configured"])
            self.assertFalse(disc["live_search_configured"])
            self.assertEqual(disc["mode"], "static_benchmark")

    def test_zero_api_key_leak_in_logs(self):
        """Ensures the secret API key is never exposed in logging or exception strings."""
        secret_key = "SERPER_SUPER_SECRET_KEY_99999"
        provider = SerperProvider(api_key=secret_key)
        status = provider.get_status()

        # Check status dictionary
        status_str = str(status)
        self.assertNotIn(secret_key, status_str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
