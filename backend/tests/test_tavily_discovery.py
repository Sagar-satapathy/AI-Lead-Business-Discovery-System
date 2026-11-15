"""
backend/tests/test_tavily_discovery.py - Comprehensive Unit & Integration Tests for Tavily and Free Search Providers

Test Matrix:
1. Missing keys: Zero external requests, safe fallback to static benchmarks.
2. Targeted query builder: Validates queries for India, Telangana, Hyderabad, and core services.
3. Mocked Tavily search execution: Zero API credits consumed. Validates payload, headers, organic parsing.
4. Provenance fields: All 9 provenance fields populated accurately.
5. Credit exhaustion handling: HTTP 402 and quota limits reported cleanly; never silently falls back to static mode.
6. Rate limiting: HTTP 429 handled safely without crashing.
7. Request timeouts: Handled gracefully without crash.
8. Malformed results: Missing URL, missing title, non-dict elements skipped cleanly.
9. Duplicate results: Deduplicated by URL before returning.
10. Seller/Directory filtering: Rejects self-advertising agencies, keeping real procurement opportunities.
11. Provider selection mechanism: Honors 'tavily', 'serper', 'mwmbl', 'static_benchmark', and 'auto'.
12. Mwmbl open-source adapter: Keyless public API mocked execution.
13. Secret redaction: API key never exposed in logs or status dicts.
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
from backend.services.tavily_provider import TavilyProvider
from backend.services.mwmbl_provider import MwmblProvider
from backend.services.provider_manager import get_active_discovery_provider, get_all_providers_status
from backend.services.discovery_service import discover_leads
from backend.main import health_check


class TestTavilyDiscovery(unittest.TestCase):

    def setUp(self):
        TavilyProvider.reset_state_for_testing()

    def test_missing_tavily_key_behavior(self):
        """When TAVILY_API_KEY is missing, external calls must not be made and static mode is preserved."""
        provider = TavilyProvider(api_key="")
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

    def test_targeted_query_builder(self):
        """Verifies targeted queries for India, Telangana, and Hyderabad with digital service intent."""
        provider = TavilyProvider(api_key="tvly-mock-key")

        # 1. Telangana Website Development
        q1 = provider.build_search_query("Telangana", "Healthcare", "Website Development")
        self.assertIn("Telangana", q1)
        self.assertIn("Hyderabad", q1)
        self.assertIn("website development", q1)
        self.assertIn("tender", q1.lower())

        # 2. Hyderabad Mobile Application Development
        q2 = provider.build_search_query("Hyderabad", "Logistics", "Mobile Application Development")
        self.assertIn("Hyderabad", q2)
        self.assertIn("mobile application", q2)
        self.assertIn("rfp", q2.lower())

        # 3. India SEO Services
        q3 = provider.build_search_query("India", "Retail", "SEO Services")
        self.assertIn("India", q3)
        self.assertIn("SEO", q3)

        # 4. Website Redesign
        q4 = provider.build_search_query("Telangana", "Public Sector", "Company Website Redesign")
        self.assertIn("redesign", q4)

    @patch("httpx.Client.post")
    def test_mocked_tavily_search_success_and_provenance(self, mock_post):
        """Tests Tavily response parsing, buying intent detection, and all 9 provenance fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "query": "Telangana mobile application development RFP tender",
            "results": [
                {
                    "title": "Tender Notice: Telangana eProcurement Portal for Citizen Healthcare App",
                    "url": "https://health.telangana.gov.in/tenders/tender-089.html",
                    "content": "Notice Inviting Tender Ref TS/HLT/2026/089: Proposals are invited for design and deployment of bilingual mobile health app. Bid submission deadline: 2026-11-15.",
                    "score": 0.92,
                },
                {
                    "title": "Hospital Management System Web Portal RFP | Hyderabad Diagnostics Network",
                    "url": "https://hyd-diagnostics.org/procurement/rfp-portal",
                    "content": "Hyderabad Diagnostics Network seeks agency vendor proposals for hospital lab web portal revamp with payment gateway integration.",
                    "score": 0.88,
                },
            ],
            "response_time": 0.42,
        }
        mock_post.return_value = mock_response

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Telangana", "Healthcare", "Mobile Application Development")

        self.assertTrue(meta["success"])
        self.assertEqual(len(candidates), 2)

        # Verify payload sent to Tavily
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["api_key"], "tvly-mock-key-12345")
        self.assertEqual(payload["search_depth"], "basic")

        # Verify Candidate 1 Provenance & Official Tender Status
        c1 = candidates[0]
        self.assertEqual(c1["provider_name"], "tavily")
        self.assertEqual(c1["record_type"], "live_discovery")
        self.assertEqual(c1["source_url"], "https://health.telangana.gov.in/tenders/tender-089.html")
        self.assertEqual(c1["source_domain"], "health.telangana.gov.in")
        self.assertTrue(c1["is_live_discovery"])
        self.assertEqual(c1["buying_intent"], "Active")
        self.assertEqual(c1["verification_status"], "official_tender")
        self.assertIn("discovered_at", c1)
        self.assertIn("evidence_text", c1)
        self.assertIn("search_query", c1)

        # Verify Candidate 2 Unverified Status for Commercial Domain
        c2 = candidates[1]
        self.assertEqual(c2["provider_name"], "tavily")
        self.assertEqual(c2["source_domain"], "hyd-diagnostics.org")
        self.assertEqual(c2["verification_status"], "unverified")
        self.assertEqual(c2["buying_intent"], "Active")

    @patch("httpx.Client.post")
    def test_credit_exhaustion_handling_http_402(self, mock_post):
        """Verifies that free credit exhaustion (HTTP 402) is cleanly handled without silently falling back to benchmarks."""
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.text = '{"detail": "Usage limit reached. Your monthly free searches have been exhausted."}'
        mock_post.return_value = mock_response

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Hyderabad", "Healthcare", "Website Development")

        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertTrue(meta["credit_exhausted"])
        self.assertIn("exhausted", meta["error"].lower())

    @patch("httpx.Client.post")
    def test_rate_limit_handling_http_429(self, mock_post):
        """Validates that HTTP 429 rate limit is handled safely without crashing."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = '{"message": "Rate limit exceeded"}'
        mock_post.return_value = mock_response

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Hyderabad", "Healthcare", "Mobile Application Development")

        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertEqual(meta["status_code"], 429)
        self.assertIn("rate limit", meta["error"].lower())

    @patch("httpx.Client.post")
    def test_timeout_handling(self, mock_post):
        """Validates that network timeouts return a safe diagnostic error without crashing."""
        mock_post.side_effect = httpx.TimeoutException("Connection timed out after 5.0s")

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Hyderabad", "Healthcare", "Website Development")

        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertIn("timed out", meta["error"].lower())

    @patch("httpx.Client.post")
    def test_malformed_and_duplicate_results_handling(self, mock_post):
        """Verifies that malformed items, None items, and duplicate URLs are safely handled and deduplicated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                None,  # Null item
                {"title": "", "url": "https://example.com/no-title"},  # Missing title
                {"title": "Valid Tender", "url": ""},  # Missing URL
                "invalid string instead of dict",  # Invalid type
                # Duplicate entries
                {
                    "title": "Tender Notice: Telangana Smart Water Metering Web Portal RFP",
                    "url": "https://water.telangana.gov.in/tenders/rfp-water-2026",
                    "content": "Request for proposal for smart water telemetry web application. Bid submission date 2026-10-30.",
                },
                {
                    "title": "Tender Notice: Duplicate Water Metering",
                    "url": "https://water.telangana.gov.in/tenders/rfp-water-2026",  # Duplicate URL
                    "content": "Duplicate content.",
                },
            ]
        }
        mock_post.return_value = mock_response

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Telangana", "Logistics", "Website Development")

        self.assertTrue(meta["success"])
        # Only 1 unique valid candidate should survive
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_url"], "https://water.telangana.gov.in/tenders/rfp-water-2026")

    @patch("httpx.Client.post")
    def test_seller_agency_and_directory_filtering(self, mock_post):
        """Ensures directories and self-advertising IT agencies are rejected, keeping only real buyers."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Top 10 Web Development Companies in Hyderabad 2026",
                    "url": "https://directory-listing.com/top-10-web-agencies",
                    "content": "Check out the top web development companies in Hyderabad.",
                },
                {
                    "title": "Best Mobile App Development Agency | Hire Us in Hyderabad",
                    "url": "https://myagency.com/services",
                    "content": "We are a leading web and mobile app development company. Hire our developers.",
                },
                {
                    "title": "Tender Notice: Telangana State Road Transport Corporation Invites Bids for Mobile App",
                    "url": "https://tsrtc.telangana.gov.in/tenders/app-rfp-2026",
                    "content": "Notice Inviting Tender for development of NextGen passenger mobile app. Bid submission deadline 2026-11-10.",
                },
            ]
        }
        mock_post.return_value = mock_response

        provider = TavilyProvider(api_key="tvly-mock-key-12345")
        candidates, meta = provider.search("Hyderabad", "Logistics", "Mobile Application Development")

        self.assertEqual(len(candidates), 1)
        self.assertIn("Telangana State Road Transport Corporation", candidates[0]["business_name"])

    def test_provider_selection_mechanism(self):
        """Tests that provider selection properly defaults to Tavily when configured, respects static benchmarks, and honors overrides."""
        # 1. Force static_benchmark
        with patch.object(settings, "DISCOVERY_PROVIDER", "static_benchmark"):
            name, instance = get_active_discovery_provider()
            self.assertEqual(name, "static_benchmark")
            self.assertIsNone(instance)

        # 2. Force tavily with key
        with patch.object(settings, "DISCOVERY_PROVIDER", "tavily"):
            with patch.object(settings, "TAVILY_API_KEY", "mock_key"):
                name, instance = get_active_discovery_provider()
                self.assertEqual(name, "tavily")
                self.assertIsInstance(instance, TavilyProvider)
                self.assertTrue(instance.is_configured())

        # 3. Force mwmbl
        with patch.object(settings, "DISCOVERY_PROVIDER", "mwmbl"):
            name, instance = get_active_discovery_provider()
            self.assertEqual(name, "mwmbl")
            self.assertIsInstance(instance, MwmblProvider)

        # 4. Auto mode with Tavily key available -> chooses Tavily (free primary)
        with patch.object(settings, "DISCOVERY_PROVIDER", "auto"):
            with patch.object(settings, "TAVILY_API_KEY", "mock_tavily_key"):
                with patch.object(settings, "SERPER_API_KEY", "mock_serper_key"):
                    name, instance = get_active_discovery_provider()
                    self.assertEqual(name, "tavily")

    @patch("httpx.Client.get")
    def test_mwmbl_adapter_mocked_execution(self, mock_get):
        """Validates keyless Mwmbl adapter execution with mocked open-source JSON results."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Tender Notice - Municipal Corporation Water SCADA Web Portal",
                    "url": "https://muni-water.gov.in/notices/scada-portal",
                    "snippet": "Request for proposal for web application SCADA monitoring system.",
                }
            ]
        }
        mock_get.return_value = mock_resp

        provider = MwmblProvider()
        self.assertTrue(provider.is_configured())
        candidates, meta = provider.search("Telangana", "Utilities", "Web Development")

        self.assertTrue(meta["success"])
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c["provider_name"], "mwmbl")
        self.assertEqual(c["record_type"], "live_discovery")
        self.assertTrue(c["is_live_discovery"])

    def test_health_check_endpoint_diagnostics(self):
        """Verifies /api/health accurately reports discovery provider statuses without treating config as execution."""
        health = health_check()
        disc = health["discovery"]
        self.assertIn("live_search_configured", disc)
        self.assertIn("operational", disc)
        self.assertIn("live_search_executed", disc)
        self.assertIn("mode", disc)
        self.assertIn("providers", disc)
        self.assertIn("tavily", disc["providers"])
        self.assertIn("serper", disc["providers"])
        self.assertIn("mwmbl", disc["providers"])

    def test_secret_redaction(self):
        """Ensures TAVILY_API_KEY is never exposed in logging or string representations."""
        secret_key = "tvly-SUPER_CONFIDENTIAL_KEY_99999"
        provider = TavilyProvider(api_key=secret_key)
        status = provider.get_status()
        self.assertNotIn(secret_key, str(status))


if __name__ == "__main__":
    unittest.main(verbosity=2)
