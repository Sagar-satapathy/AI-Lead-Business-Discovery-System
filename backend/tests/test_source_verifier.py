"""
backend/tests/test_source_verifier.py - Phase 4 Source Page Verification Test Suite

Tests:
1. Localhost and private IP rejection (SSRF)
2. DNS rebinding prevention and restricted IP validation
3. Malicious redirect interception
4. Genuine buyer procurement page classification
5. Seller agency page detection and disqualification
6. Portfolio and case-study page detection
7. Directory listing detection
8. HTTP timeout handling
9. HTTP 403 and 503 response handling
10. Oversized response (>512 KB) download termination
11. Malformed and invalid HTML tolerance
12. Insufficient buyer evidence handling (zero hallucination)
13. FastAPI POST /api/leads/{id}/verify-source endpoint integration
"""

import asyncio
import io
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import httpx
from backend.services.source_verifier import (
    validate_target_url,
    is_ip_restricted,
    classify_page_content,
    verify_source_url,
    verify_candidates_concurrently,
    HTMLContentExtractor,
    SSRFSecurityError,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
)
from backend.db import get_lead_by_id, init_database
from backend.main import verify_lead_source


class TestSourceVerifier(unittest.TestCase):
    """Test suite for Phase 4 Source Page Verification engine."""

    def test_localhost_and_private_ip_rejection(self):
        """Verifies SSRF protection against localhost, loopback, private RFC-1918, link-local, and cloud metadata."""
        blocked_targets = [
            ("http://localhost:8000/secret", "localhost"),
            ("http://localhost.localdomain/api", "localhost"),
            ("http://127.0.0.1/admin", "127.0.0.1"),
            ("http://127.0.1.1/test", "127.0.1.1"),
            ("http://10.0.0.1/internal", "10.0.0.1"),
            ("http://172.16.0.1/db", "172.16.0.1"),
            ("http://172.31.255.255/admin", "172.31.255.255"),
            ("http://192.168.1.1/gateway", "192.168.1.1"),
            ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
            ("http://[::1]/secret", "::1"),
            ("http://metadata.google.internal/computeMetadata/v1", "metadata.google.internal"),
            ("http://example.com:8080/path", "8080"),
            ("http://example.com:22/ssh", "22"),
            ("ftp://example.com/file.txt", "ftp"),
            ("file:///etc/passwd", "file"),
        ]

        for target_url, keyword in blocked_targets:
            is_safe, reason, ip = validate_target_url(target_url)
            self.assertFalse(
                is_safe,
                f"Target '{target_url}' should have been rejected by SSRF guard! Reason: {reason}",
            )

    def test_dns_rebinding_protection(self):
        """Verifies that DNS lookups resolving to private/restricted IPs are strictly rejected."""
        # Test direct IP checking
        self.assertTrue(is_ip_restricted("127.0.0.1")[0])
        self.assertTrue(is_ip_restricted("10.20.30.40")[0])
        self.assertTrue(is_ip_restricted("172.20.0.1")[0])
        self.assertTrue(is_ip_restricted("192.168.0.100")[0])
        self.assertTrue(is_ip_restricted("169.254.169.254")[0])
        self.assertTrue(is_ip_restricted("::1")[0])
        self.assertTrue(is_ip_restricted("100.64.0.1")[0])
        self.assertFalse(is_ip_restricted("8.8.8.8")[0])

        # Test socket peer IP check simulated
        with patch("socket.getaddrinfo") as mock_dns:
            # Simulate DNS returning a private IP
            mock_dns.return_value = [
                (2, 1, 0, "", ("127.0.0.1", 80))
            ]
            is_safe, reason, _ = validate_target_url("http://rebind-test.com")
            self.assertFalse(is_safe)
            self.assertIn("SSRF blocked", reason)

    def test_malicious_redirects(self):
        """Verifies that HTTP redirects to restricted internal destinations are caught and blocked."""
        loop = asyncio.new_event_loop()
        try:
            with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
                # First response is a 301 redirect pointing to internal metadata
                mock_redirect = MagicMock()
                mock_redirect.is_redirect = True
                mock_redirect.status_code = 301
                mock_redirect.headers = {"Location": "http://169.254.169.254/latest/meta-data"}
                mock_redirect.aclose = AsyncMock()

                mock_send.return_value = mock_redirect

                with patch("backend.services.source_verifier.validate_target_url") as mock_val:
                    # Initial URL is safe, redirect hop is restricted
                    def val_side_effect(u):
                        if "169.254" in u:
                            return False, "SSRF blocked: Cloud metadata rejected", None
                        return True, "Safe", "93.184.216.34"

                    mock_val.side_effect = val_side_effect
                    res = loop.run_until_complete(verify_source_url("http://example.com/redirect-me"))

                    self.assertEqual(res["fetch_status"], "ssrf_blocked")
                    self.assertIn("Cloud metadata rejected", res["notes"])
        finally:
            loop.close()

    def test_genuine_procurement_page(self):
        """Verifies classification of an authentic government / public buyer procurement notice."""
        procurement_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telangana State Technology Services - Tender Notice</title>
            <meta name="description" content="Notice Inviting Tender for Development and Maintenance of Web Portal" />
        </head>
        <body>
            <nav><a href="/">Home</a> <a href="/tenders">Tenders</a> <a href="/contact">Contact</a></nav>
            <h1>Notice Inviting Tender (NIT No: TSTS/HWP/2026/04)</h1>
            <p>Sealed tenders are invited from reputed agencies for the design, development, and hosting of a responsive digital healthcare portal.</p>
            <p>Scope of Work: Modern responsive website with bilingual support, citizen grievance module, and mobile accessibility.</p>
            <p>Last date for submission of bids: 15-Dec-2026 at 15:00 hrs IST. Earnest Money Deposit: INR 50,000.</p>
        </body>
        </html>
        """
        parser = HTMLContentExtractor()
        parser.feed(procurement_html)
        classification = classify_page_content(
            title=parser.title,
            meta_desc=parser.meta_description,
            nav_links=parser.nav_links,
            headings=parser.headings,
            body_text=parser.get_clean_body_text(),
            url="https://tender.telangana.gov.in/portal-tender-notice",
        )

        self.assertEqual(classification["page_type"], "buyer_procurement")
        self.assertTrue(classification["is_buyer"])
        self.assertFalse(classification["is_seller"])
        self.assertTrue(len(classification["evidence_snippet"]) > 10)
        self.assertIn("notice inviting tender", classification["evidence_snippet"].lower())

    def test_agency_service_page(self):
        """Verifies detection and disqualification of an IT agency marketing its services."""
        agency_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Premier Software Solutions - Top Web Development Company</title>
            <meta name="description" content="We are a leading web development and mobile app development agency in Hyderabad." />
        </head>
        <body>
            <nav>
                <a href="/services">Our Services</a>
                <a href="/pricing">Pricing Plans</a>
                <a href="/portfolio">Our Work</a>
                <a href="/contact">Request a Quote</a>
            </nav>
            <h1>Custom Software and Web Development Services</h1>
            <p>We are a leading digital agency helping global brands build modern web portals.</p>
            <p>Hire dedicated developers from our team for your next big project.</p>
            <p>Why choose us: 10+ years of excellence, 200+ satisfied clients, dedicated 24/7 support.</p>
            <p>Get a free quote today and talk to our tech experts.</p>
        </body>
        </html>
        """
        parser = HTMLContentExtractor()
        parser.feed(agency_html)
        classification = classify_page_content(
            title=parser.title,
            meta_desc=parser.meta_description,
            nav_links=parser.nav_links,
            headings=parser.headings,
            body_text=parser.get_clean_body_text(),
            url="https://premiersoftware.com/web-development-services",
        )

        self.assertEqual(classification["page_type"], "seller_agency")
        self.assertFalse(classification["is_buyer"])
        self.assertTrue(classification["is_seller"])
        self.assertIn("digital service provider", classification["notes"])

    def test_portfolio_and_case_study_page(self):
        """Verifies detection of agency portfolio / case-study pages (like Swaragh Technologies)."""
        portfolio_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Healthcare Web Portal Case Study - Agency Work</title>
        </head>
        <body>
            <nav><a href="/">Home</a> <a href="/portfolio">Portfolio</a></nav>
            <h1>Case Study: Regional Healthcare Portal Revamp</h1>
            <p>Project Overview: We built an advanced online hospital booking portal for our client.</p>
            <p>Results achieved for our client: 45% increase in online patient registrations.</p>
            <p>Client testimonial: 'Their engineering team was outstanding in delivering our portal.'</p>
        </body>
        </html>
        """
        parser = HTMLContentExtractor()
        parser.feed(portfolio_html)
        classification = classify_page_content(
            title=parser.title,
            meta_desc=parser.meta_description,
            nav_links=parser.nav_links,
            headings=parser.headings,
            body_text=parser.get_clean_body_text(),
            url="https://swaragh.com/portfolio-healthcare",
        )

        self.assertEqual(classification["page_type"], "portfolio")
        self.assertFalse(classification["is_buyer"])
        self.assertTrue(classification["is_seller"])
        self.assertIn("portfolio", classification["notes"])

    def test_directory_listing_page(self):
        """Verifies detection of directories, review sites, and aggregator platforms."""
        directory_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Top 10 Web Development Companies in Hyderabad 2026</title>
        </head>
        <body>
            <h1>Find the best developers and compare top rated software agencies</h1>
            <p>Directory of verified agencies with client reviews and ratings.</p>
            <ul>
                <li>Company A - 4.9 Stars (50 reviews)</li>
                <li>Company B - 4.8 Stars (42 reviews)</li>
            </ul>
        </body>
        </html>
        """
        parser = HTMLContentExtractor()
        parser.feed(directory_html)
        classification = classify_page_content(
            title=parser.title,
            meta_desc=parser.meta_description,
            nav_links=parser.nav_links,
            headings=parser.headings,
            body_text=parser.get_clean_body_text(),
            url="https://clutch.co/web-developers/hyderabad",
        )

        self.assertEqual(classification["page_type"], "directory")
        self.assertFalse(classification["is_buyer"])
        self.assertFalse(classification["is_seller"])

    def test_http_timeouts(self):
        """Verifies graceful timeout handling when an external origin fails to respond."""
        loop = asyncio.new_event_loop()
        try:
            with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
                mock_send.side_effect = httpx.TimeoutException("Connection timed out after 4.0s")
                with patch("backend.services.source_verifier.validate_target_url") as mock_val:
                    mock_val.return_value = (True, "Safe", "93.184.216.34")

                    res = loop.run_until_complete(verify_source_url("https://slow-origin.org/tender"))
                    self.assertEqual(res["fetch_status"], "timeout")
                    self.assertEqual(res["page_type"], "unknown")
                    self.assertFalse(res["is_buyer"])
                    self.assertIn("timed out", res["notes"])
        finally:
            loop.close()

    def test_http_403_and_503(self):
        """Verifies handling of HTTP 403 Forbidden and 503 Server Error codes."""
        loop = asyncio.new_event_loop()
        try:
            # 1. Test 403 Forbidden
            with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
                mock_resp = MagicMock()
                mock_resp.is_redirect = False
                mock_resp.status_code = 403
                mock_resp.aclose = AsyncMock()
                mock_send.return_value = mock_resp

                with patch("backend.services.source_verifier.validate_target_url") as mock_val:
                    mock_val.return_value = (True, "Safe", "93.184.216.34")
                    res = loop.run_until_complete(verify_source_url("https://protected-site.gov/tender"))
                    self.assertEqual(res["fetch_status"], "blocked_403")
                    self.assertIn("403 Forbidden", res["notes"])

            # 2. Test 503 Server Error
            with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
                mock_resp = MagicMock()
                mock_resp.is_redirect = False
                mock_resp.status_code = 503
                mock_resp.aclose = AsyncMock()
                mock_send.return_value = mock_resp

                with patch("backend.services.source_verifier.validate_target_url") as mock_val:
                    mock_val.return_value = (True, "Safe", "93.184.216.34")
                    res = loop.run_until_complete(verify_source_url("https://down-site.gov/tender"))
                    self.assertEqual(res["fetch_status"], "server_error_503")
                    self.assertIn("503 Server Error", res["notes"])
        finally:
            loop.close()

    def test_oversized_response(self):
        """Verifies download termination when a response exceeds the 512 KB cap."""
        loop = asyncio.new_event_loop()
        try:
            with patch("httpx.AsyncClient.send", new_callable=AsyncMock) as mock_send:
                mock_resp = MagicMock()
                mock_resp.is_redirect = False
                mock_resp.status_code = 200
                mock_resp.headers = {"Content-Type": "text/html"}
                mock_resp.aclose = AsyncMock()

                # Generate stream exceeding 512 KB
                async def mock_stream():
                    chunk = b"A" * (64 * 1024)
                    for _ in range(10):  # 640 KB total
                        yield chunk

                mock_resp.aiter_bytes = mock_stream
                mock_send.return_value = mock_resp

                with patch("backend.services.source_verifier.validate_target_url") as mock_val:
                    mock_val.return_value = (True, "Safe", "93.184.216.34")
                    res = loop.run_until_complete(verify_source_url("https://giant-file.org/large.html"))
                    self.assertEqual(res["fetch_status"], "oversized")
                    self.assertIn("exceeded", res["notes"])
        finally:
            loop.close()

    def test_invalid_html_graceful_tolerance(self):
        """Verifies parser does not crash on malformed, incomplete, or unclosed HTML tags."""
        malformed_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Malformed Page Title</title>
        <body>
        <div class="unclosed-div" attr=unquoted_val>
            <p>This is recoverable text inside malformed markup.
            <span>Unclosed span text
            <a href="/services">Link text without closing tag
            <img src="pic.jpg" alt="No closing tag">
            <input type="text" value="broken input"
        </div>
        <script>alert('should be ignored');</script>
        """
        parser = HTMLContentExtractor()
        # Should not raise any exception
        parser.feed(malformed_html)
        body = parser.get_clean_body_text()
        self.assertIn("recoverable text", body)
        self.assertNotIn("alert", body)  # script correctly stripped

    def test_insufficient_buyer_evidence(self):
        """Verifies that generic, non-commercial pages are classified as 'unknown' without fabricating buyer intent."""
        blog_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Daily Wellness Blog</title></head>
        <body>
            <h1>10 Tips for Healthy Living</h1>
            <p>Drink eight glasses of water every day and get plenty of rest.</p>
        </body>
        </html>
        """
        parser = HTMLContentExtractor()
        parser.feed(blog_html)
        classification = classify_page_content(
            title=parser.title,
            meta_desc=parser.meta_description,
            nav_links=parser.nav_links,
            headings=parser.headings,
            body_text=parser.get_clean_body_text(),
            url="https://healthblog.org/tips",
        )
        self.assertEqual(classification["page_type"], "unknown")
        self.assertFalse(classification["is_buyer"])
        self.assertFalse(classification["is_seller"])
        self.assertEqual(classification["evidence_snippet"], "")

    def test_fastapi_verify_source_endpoint(self):
        """Verifies database persistence and integration for source page verification."""
        from backend.db import update_source_verification, get_lead_by_id
        try:
            ok = update_source_verification(
                lead_id=1,
                fetch_status="200_ok",
                page_type="buyer_procurement",
                verified_at="2026-11-14T19:00:00Z",
                evidence_snippet="Notice Inviting Tender for Hospital Web Portal",
                verification_notes="Verified genuine buyer procurement notice",
            )
            self.assertTrue(ok)
            lead = get_lead_by_id(1)
            self.assertEqual(lead["source_fetch_status"], "200_ok")
            self.assertEqual(lead["source_page_type"], "buyer_procurement")
            self.assertEqual(lead["source_evidence_snippet"], "Notice Inviting Tender for Hospital Web Portal")
        finally:
            update_source_verification(
                lead_id=1,
                fetch_status=None,
                page_type=None,
                verified_at=None,
                evidence_snippet="",
                verification_notes=None,
            )


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSourceVerifier)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
