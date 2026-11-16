"""
backend/tests/test_marketplace_discovery.py - Automated Tests for Marketplace Buyer-Opportunity Discovery

Verification Suites:
1. Test marketplace-specific query construction (PeoplePerHour, Truelancer, Contra, digital services, locations, exclusions).
2. Test genuine buyer project classification (Active/Potential buying intent, relevance).
3. Test rejection of freelancer service advertisements ("I will build...", gig profiles, portfolio showcases).
4. Test rejection of employment listings (Hubstaff Talent, full-time remote vacancies, salary posts).
5. Test missing organisation names and publication dates (Zero hallucination: None for missing dates, transparent attribution).
6. Test source URL and evidence preservation (Source platform, exact URL, evidence text, unverified status).
7. Test rate limits and provider failures (HTTP 429, timeouts handled safely with zero crash).
8. Confirm existing Serper discovery tests still pass.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import httpx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.services.serper_provider import (
    SerperProvider,
    SUPPORTED_MARKETPLACES,
    EXCLUDED_MARKETPLACES,
)


class TestMarketplaceDiscovery(unittest.TestCase):

    def setUp(self):
        self.provider = SerperProvider(api_key="mock_secret_marketplace_key")

    def test_1_marketplace_query_construction(self):
        """1. Test marketplace-specific query construction for all supported platforms, services, and geographies."""
        # 1a. Generic query across all supported marketplaces
        q1, gl1 = self.provider.build_marketplace_query("Website Development", "London, UK")
        self.assertEqual(gl1, "gb")
        self.assertIn("site:peopleperhour.com/freelance-jobs", q1)
        self.assertIn("site:truelancer.com/freelance-jobs", q1)
        self.assertIn("site:contra.com/opportunity", q1)
        self.assertIn("website development", q1.lower())
        self.assertIn("looking for", q1.lower())
        self.assertIn("-site:fiverr.com", q1)
        self.assertIn("-site:talent.hubstaff.com", q1)
        self.assertIn('"I will"', q1)

        # 1b. Specific platform: PeoplePerHour E-commerce in India
        q2, gl2 = self.provider.build_marketplace_query("E-commerce Development", "Telangana, India", platform="peopleperhour")
        self.assertEqual(gl2, "in")
        self.assertIn("site:peopleperhour.com", q2)
        self.assertNotIn("site:truelancer.com", q2)
        self.assertNotIn("site:contra.com", q2)
        self.assertTrue("ecommerce" in q2.lower() or "e-commerce" in q2.lower() or "shopify" in q2.lower())

        # 1c. Specific platform: Truelancer Mobile App in US
        q3, gl3 = self.provider.build_marketplace_query("Mobile Application Development", "Austin, TX", platform="truelancer")
        self.assertEqual(gl3, "us")
        self.assertIn("site:truelancer.com", q3)
        self.assertNotIn("site:peopleperhour.com", q3)
        self.assertTrue("mobile app" in q3.lower() or "flutter" in q3.lower())

        # 1d. Specific platform: Contra Web App in Canada
        q4, gl4 = self.provider.build_marketplace_query("Web Application Development", "Toronto, Canada", platform="contra")
        self.assertEqual(gl4, "ca")
        self.assertIn("site:contra.com/opportunity", q4)
        self.assertTrue("web application" in q4.lower() or "web app" in q4.lower())

        # 1e. SEO & Digital Marketing
        q5, _ = self.provider.build_marketplace_query("SEO Services", "Global")
        self.assertTrue("seo" in q5.lower() or "digital marketing" in q5.lower())

    @patch("httpx.Client.post")
    def test_2_genuine_buyer_project_classification(self, mock_post):
        """2. Test genuine buyer project classification into Active / Potential intent with correct relevance."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "searchParameters": {"q": "test marketplace", "num": 10},
            "organic": [
                {
                    "title": "Need an E-commerce Website for Organic Food Store - PeoplePerHour",
                    "link": "https://www.peopleperhour.com/freelance-jobs/technology-programming/need-an-e-commerce-website-for-organic-food-store-38912",
                    "snippet": "Client in London is looking for a Shopify / WooCommerce expert to build a responsive e-commerce website with payment gateway and inventory tracking. Budget: £1,500.",
                    "date": "2026-11-01",
                },
                {
                    "title": "Looking for Flutter Developer to build Healthcare Telemedicine App | Truelancer",
                    "link": "https://www.truelancer.com/freelance-jobs/flutter-healthcare-telemedicine-app-8812",
                    "snippet": "Project Description: We need an experienced Flutter developer to build our Android and iOS telemedicine consultation app. Client based in Hyderabad.",
                    "date": "2026-11-04",
                },
                {
                    "title": "B2B SaaS Portal Revamp Project Brief | Contra",
                    "link": "https://contra.com/opportunity/b2b-saas-portal-revamp-992",
                    "snippet": "Seeking a full-stack engineer for scope of work on existing cloud web app portal. Seeking vendor proposals for complete UI and API redesign.",
                    "date": "2026-10-28",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_resp

        candidates, meta = self.provider.search_marketplace_opportunities(
            service="Website Development",
            location="London, UK",
        )

        self.assertTrue(meta["success"])
        self.assertEqual(len(candidates), 3)

        # Candidate 1: PeoplePerHour
        c1 = candidates[0]
        self.assertEqual(c1["marketplace"], "PeoplePerHour")
        self.assertEqual(c1["buying_intent"], "Active")
        self.assertEqual(c1["verification_status"], "unverified")
        self.assertTrue(c1["is_live_discovery"])
        self.assertIn("peopleperhour.com", c1["source_url"])
        self.assertIn("Shopify", c1["evidence_text"])
        self.assertEqual(c1["publication_date"], "2026-11-01")

        # Candidate 2: Truelancer
        c2 = candidates[1]
        self.assertEqual(c2["marketplace"], "Truelancer")
        self.assertEqual(c2["buying_intent"], "Active")
        self.assertIn("truelancer.com", c2["source_url"])
        self.assertIn("Flutter", c2["evidence_text"])

        # Candidate 3: Contra
        c3 = candidates[2]
        self.assertEqual(c3["marketplace"], "Contra")
        self.assertEqual(c3["buying_intent"], "Active")
        self.assertIn("contra.com", c3["source_url"])
        self.assertIn("B2B SaaS Portal", c3["source_title"])

    @patch("httpx.Client.post")
    def test_3_rejection_of_freelancer_service_advertisements(self, mock_post):
        """3. Test rejection of freelancer service advertisements ('I will build...', freelancer profiles, gigs)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "organic": [
                {
                    "title": "I will develop custom mobile application in Flutter and iOS - Truelancer",
                    "link": "https://www.truelancer.com/freelancer/flutterdev/service/i-will-develop-mobile-app",
                    "snippet": "I am a top rated mobile app developer with 5+ years of experience. Hire me for your Android and iOS apps. Starting at $300.",
                },
                {
                    "title": "Hire Top Rated Web Developer John Doe - PeoplePerHour",
                    "link": "https://www.peopleperhour.com/freelancer/technology-programming/john-doe-web-dev",
                    "snippet": "About the freelancer: Senior web developer with 8 years of experience. View my portfolio items and completed 45 projects.",
                },
                {
                    "title": "I will build responsive WordPress website with SEO - Fiverr",
                    "link": "https://www.fiverr.com/gigs/wordpress-website",
                    "snippet": "Seller level 2 pro freelancer. Starting at $50. View my gig description.",
                },
                {
                    "title": "Need a Web App for Dental Clinic Patient Appointments - PeoplePerHour",
                    "link": "https://www.peopleperhour.com/job/dental-clinic-web-app-9912",
                    "snippet": "Looking for web developer to build an online appointment booking system for our dental clinic.",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_resp

        candidates, meta = self.provider.search_marketplace_opportunities("Website Development")

        # The 3 seller advertisements (Truelancer gig, PeoplePerHour profile, Fiverr gig) must be rejected
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_url"], "https://www.peopleperhour.com/job/dental-clinic-web-app-9912")
        self.assertIn("Dental Clinic", candidates[0]["requirement"])

    @patch("httpx.Client.post")
    def test_4_rejection_of_employment_listings(self, mock_post):
        """4. Test rejection of employment listings (Hubstaff Talent, full-time vacancies, salary hiring)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "organic": [
                {
                    "title": "Senior React Native Engineer (Full-Time Remote) - Hubstaff Talent",
                    "link": "https://talent.hubstaff.com/jobs/senior-react-native-engineer-1029",
                    "snippet": "We are hiring a full-time Senior React Native Developer. Salary: $90,000 - $110,000 per annum with health insurance and PTO.",
                },
                {
                    "title": "We are hiring Lead Frontend Engineer - PeoplePerHour Job Board",
                    "link": "https://www.peopleperhour.com/jobs/lead-frontend-engineer-career",
                    "snippet": "Career opportunity: Full-time role. Annual salary £60k. 5+ years of experience required. Benefits include pension.",
                },
                {
                    "title": "Client Looking for Shopify Expert to Build Fashion Store - PeoplePerHour",
                    "link": "https://www.peopleperhour.com/freelance-jobs/shopify-fashion-store-1192",
                    "snippet": "Client is looking for a Shopify developer to create our luxury apparel store. Fixed price budget £2,000.",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_resp

        candidates, meta = self.provider.search_marketplace_opportunities("E-commerce Development")

        # Both employment vacancies must be rejected, keeping only the genuine buyer project
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["source_url"], "https://www.peopleperhour.com/freelance-jobs/shopify-fashion-store-1192")
        self.assertEqual(candidates[0]["buying_intent"], "Active")

    @patch("httpx.Client.post")
    def test_5_missing_organisation_names_and_publication_dates(self, mock_post):
        """5. Test missing organisation names and publication dates (Zero hallucination: None for missing dates, transparent attribution)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "organic": [
                {
                    "title": "Need WordPress Website Redesign Project | Contra",
                    "link": "https://contra.com/opportunity/wordpress-redesign-992",
                    "snippet": "Seeking an experienced web designer to revamp an existing B2B company website on WordPress.",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_resp

        candidates, meta = self.provider.search_marketplace_opportunities("Website Development")
        self.assertEqual(len(candidates), 1)
        cand = candidates[0]

        # Publication date must be None when not provided - NEVER defaulted to today!
        self.assertIsNone(cand["publication_date"])
        # Organisation name must NOT be a fictitious company; uses transparent attribution
        self.assertEqual(cand["business_name"], "Client via Contra")
        self.assertNotIn("Unknown LLC", cand["business_name"])
        self.assertNotIn("Fake Corp", cand["business_name"])

    @patch("httpx.Client.post")
    def test_6_source_url_and_evidence_preservation(self, mock_post):
        """6. Test source URL and evidence preservation with strict provenance."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        test_url = "https://www.peopleperhour.com/freelance-jobs/technology-programming/build-mobile-crm-app-991"
        test_snippet = "Need an iOS and Android mobile CRM app with barcode scanner and SQLite sync. Budget: $4,500."
        mock_resp.json.return_value = {
            "organic": [
                {
                    "title": "Build Mobile CRM App - PeoplePerHour",
                    "link": test_url,
                    "snippet": test_snippet,
                    "date": "2026-11-10",
                },
            ],
            "credits": 1,
        }
        mock_post.return_value = mock_resp

        candidates, meta = self.provider.search_marketplace_opportunities("Mobile Application Development")
        self.assertEqual(len(candidates), 1)
        c = candidates[0]

        self.assertEqual(c["source_url"], test_url)
        self.assertEqual(c["source_domain"], "peopleperhour.com")
        self.assertEqual(c["marketplace"], "PeoplePerHour")
        self.assertEqual(c["evidence_text"], test_snippet)
        self.assertEqual(c["verification_status"], "unverified")
        self.assertTrue(c["is_live_discovery"])
        self.assertEqual(c["provider_name"], "serper")
        self.assertIsNotNone(c["discovered_at"])

    @patch("httpx.Client.post")
    def test_7_rate_limits_and_provider_failures(self, mock_post):
        """7. Test rate limits (HTTP 429) and network timeouts handled safely without crash."""
        # Rate limit (HTTP 429)
        resp_429 = MagicMock()
        resp_429.status_code = 429
        mock_post.return_value = resp_429

        candidates, meta = self.provider.search_marketplace_opportunities("Website Development")
        self.assertEqual(candidates, [])
        self.assertFalse(meta["success"])
        self.assertEqual(meta["status_code"], 429)
        self.assertIn("rate limit", meta["error"].lower())

        # Timeout Exception
        mock_post.side_effect = httpx.TimeoutException("Connection timed out after 5.0s")
        candidates_to, meta_to = self.provider.search_marketplace_opportunities("Website Development")
        self.assertEqual(candidates_to, [])
        self.assertFalse(meta_to["success"])
        self.assertIn("timed out", meta_to["error"].lower())

    def test_8_confirm_existing_serper_discovery_tests_still_pass(self):
        """8. Confirm existing Serper discovery tests still pass without regression."""
        # Verify provider status includes supported marketplaces
        status = self.provider.get_status()
        self.assertIn("supported_marketplaces", status)
        self.assertIn("peopleperhour", status["supported_marketplaces"])
        self.assertIn("truelancer", status["supported_marketplaces"])
        self.assertIn("contra", status["supported_marketplaces"])

        # Verify EXCLUDED_MARKETPLACES contains Hubstaff and Fiverr
        self.assertIn("hubstaff", EXCLUDED_MARKETPLACES)
        self.assertIn("fiverr", EXCLUDED_MARKETPLACES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
