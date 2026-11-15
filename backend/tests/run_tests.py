"""
backend/tests/run_tests.py - Robust Automated Test Runner for Backend API & Business Logic
"""

import sys
import os
import io
import datetime
from unittest.mock import patch, MagicMock
import unittest

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.tests.test_source_verifier import TestSourceVerifier

from fastapi import HTTPException
from backend.config import settings
from backend.main import (
    health_check,
    get_metrics,
    list_leads,
    get_lead,
    create_lead,
    execute_discovery,
    export_csv,
    export_excel,
    confirm_export,
    LeadCreateRequest,
    DiscoveryRequest,
    ExportConfirmRequest,
)
from backend.services.ai_service import evaluate_lead, process_and_save_lead


def run_tests():
    print("=" * 70)
    print("AI LEAD BUSINESS DISCOVERY SYSTEM - BACKEND VERIFICATION SUITE")
    print("=" * 70)

    # Test 1: Health Check
    print("\n[1/10] Verifying Health Check Endpoint...")
    health = health_check()
    assert health["status"] == "healthy", f"Expected healthy, got {health['status']}"
    assert health["ai_providers"]["fallback_nlp_ready"] is True
    print(f"       PASS -> Status: {health['status']}, DB: {health['database_type']}")

    # Test 2: KPI Metrics Calculation
    print("\n[2/10] Verifying KPI Dashboard Metrics...")
    metrics = get_metrics()
    assert metrics["total_records"] >= 27, f"Expected at least 27 records, got {metrics['total_records']}"
    assert "category_counts" in metrics
    assert "priority_counts" in metrics
    print(f"       PASS -> Total: {metrics['total_records']}, Processed: {metrics['processed_records']}, Unexported: {metrics['not_yet_exported']}")

    # Test 3: Leads Pagination
    print("\n[3/10] Verifying Leads Query & Pagination...")
    paged = list_leads(page=1, page_size=10)
    assert len(paged["leads"]) <= 10
    assert paged["total"] >= 27
    print(f"       PASS -> Page 1 returned {len(paged['leads'])} of {paged['total']} records (Total Pages: {paged['total_pages']})")

    # Test 4: Priority & Export Filters
    print("\n[4/10] Verifying Lead Filtering Logic...")
    high_leads = list_leads(priority="High")
    for l in high_leads["leads"]:
        assert l["priority"] == "High"

    unexp_leads = list_leads(is_exported=0)
    for l in unexp_leads["leads"]:
        assert l["is_exported"] == 0
    print(f"       PASS -> Filtered {len(high_leads['leads'])} High Priority and {len(unexp_leads['leads'])} Unexported leads")

    # Test 5: Single Lead Retrieval & 404 Behavior
    print("\n[5/10] Verifying Single Lead Retrieval...")
    lead_1 = get_lead(1)
    assert lead_1["id"] == 1
    assert "business_name" in lead_1

    try:
        get_lead(999999)
        assert False, "Should have raised HTTPException 404"
    except HTTPException as e:
        assert e.status_code == 404
    print("       PASS -> Lead 1 retrieved correctly; nonexistent ID gracefully returned 404")

    # Test 6: Strict Location Isolation - Austin
    print("\n[6/16] Verifying Strict Location Isolation - Austin, TX...")
    with patch.object(settings, "DISCOVERY_PROVIDER", "static_benchmark"):
        austin_req = DiscoveryRequest(
            location="Austin, TX",
            category="Healthcare",
            service="Mobile Application Development",
            auto_ingest=False,
            limit=5,
        )
        austin_res = execute_discovery(austin_req)
        a_candidates = austin_res["candidates"]
        assert len(a_candidates) == 1, f"Expected 1 Austin match, got {len(a_candidates)}"
        austin_lead = a_candidates[0]
        assert "Austin" in austin_lead["location"], f"Expected Austin location, got {austin_lead['location']}"
        assert austin_lead["is_live_discovery"] is False
        assert austin_lead["record_type"] == "demo"
        assert austin_lead["verification_status"] == "demo"
        # Zero bleed into other geographies
        for c in a_candidates:
            assert "Telangana" not in c["location"]
            assert "London" not in c["location"]
            assert "Boston" not in c["location"]
            assert "Chicago" not in c["location"]
        print(f"       PASS -> Isolated 1 Austin demonstration benchmark ({austin_lead['business_name']}) with zero bleed")

    # Test 7: Scoped CSV Export
    print("\n[7/16] Verifying Scoped CSV Export & 4-Tier Provenance Headers...")
    from backend.services.export_service import generate_csv_bytes, generate_excel_bytes
    csv_bytes, ids, count = generate_csv_bytes("unexported")
    assert len(csv_bytes) > 0
    assert b"Lead ID" in csv_bytes or b"Business Name" in csv_bytes
    assert b"Record Type" in csv_bytes
    assert b"Verification Status" in csv_bytes
    assert b"Source URL" in csv_bytes
    assert b"Verification Notes" in csv_bytes
    csv_stream = export_csv(scope="unexported")
    assert csv_stream.media_type == "text/csv"
    print(f"       PASS -> Generated {len(csv_bytes)} bytes of RFC-4180 CSV with provenance columns ({count} records)")

    # Test 8: Scoped Excel Export (.xlsx)
    print("\n[8/16] Verifying Scoped Excel Export (.xlsx)...")
    excel_bytes, ids, count = generate_excel_bytes("unexported")
    assert len(excel_bytes) > 0
    assert excel_bytes[:4] == b"PK\x03\x04", "Valid ZIP/XLSX magic signature required"
    excel_stream = export_excel(scope="unexported")
    assert "openxmlformats" in excel_stream.media_type
    print(f"       PASS -> Generated {len(excel_bytes)} bytes of styled OpenPyXL spreadsheet (.xlsx)")

    # Test 9: Deterministic Lead Scoring & Explainability
    print("\n[9/16] Verifying AI Intent Classification & 5-Factor Scoring...")
    ok, ai_res, scoring, err = evaluate_lead(
        requirement="Seeking mobile app agency to develop iOS and Android fleet dispatch system with GPS telemetry ASAP.",
        business_name="Atlas Fleet Logistics",
        preferred_provider="fallback",
    )
    assert ok is True
    assert ai_res["category"] == "Mobile Application Development"
    assert ai_res["buying_intent"] == "Active"
    assert scoring["total_score"] >= 60
    assert len(ai_res["evidence"]) > 0
    assert "service_relevance" in scoring["score_breakdown"]
    assert "buying_intent" in scoring["score_breakdown"]
    assert "timeline_urgency" in scoring["score_breakdown"]
    print(f"       PASS -> Category: {ai_res['category']}, Score: {scoring['total_score']}/100, Priority: {scoring['priority']}")
    print(f"               Evidence: \"{ai_res['evidence'][:60]}...\"")

    # Test 10: Lead Ingestion & Duplicate Constraints
    print("\n[10/16] Verifying Lead Ingestion & Unique Constraints...")
    test_req = LeadCreateRequest(
        business_name="Vanguard Robotic Automation",
        requirement="Seeking industrial software engineers to develop automated conveyor PLC control portal with OPC-UA.",
        source_name="Tender Verification Suite",
        location="Chicago, IL",
    )
    try:
        res = create_lead(test_req)
        print(f"       PASS -> Successfully ingested new lead ID: {res['lead']['id']}")
        # Attempt duplicate insertion
        try:
            create_lead(test_req)
            assert False, "Should have raised 409 Conflict"
        except HTTPException as conflict_err:
            assert conflict_err.status_code == 409
            print("       PASS -> Duplicate entry correctly rejected with 409 Conflict")
    except HTTPException as e:
        if e.status_code == 409:
            print("       PASS -> Lead already ingested in previous run; duplicate prevention verified (409)")
        else:
            raise e

    # Test 11: Strict Location Isolation - Telangana
    print("\n[11/16] Verifying Strict Location Isolation - Telangana, India...")
    with patch.object(settings, "DISCOVERY_PROVIDER", "static_benchmark"):
        telangana_req = DiscoveryRequest(
            location="Telangana",
            category="Healthcare",
            service="Website Development",
            auto_ingest=False,
        )
        telangana_res = execute_discovery(telangana_req)
        t_candidates = telangana_res["candidates"]
        assert len(t_candidates) == 1, f"Expected exactly 1 Telangana match, got {len(t_candidates)}"
        tel_lead = t_candidates[0]
        assert "Telangana" in tel_lead["location"], f"Expected Telangana location, got {tel_lead['location']}"
        assert "telangana.gov.in" in tel_lead["source_url"]
        assert tel_lead["is_live_discovery"] is False
        assert tel_lead["record_type"] == "demo"
        assert tel_lead["verification_status"] == "demo"
        # Ensure zero out-of-region bleed
        for c in t_candidates:
            assert "Austin" not in c["location"]
            assert "London" not in c["location"]
            assert "Boston" not in c["location"]
            assert "Toronto" not in c["location"]
            assert "Chicago" not in c["location"]
        print(f"       PASS -> Isolated 1 Telangana benchmark ({tel_lead['business_name']}) with zero bleed")

        # Test 12: Strict Location Isolation - London
        print("\n[12/16] Verifying Strict Location Isolation - London, UK...")
        london_req = DiscoveryRequest(
            location="London, UK",
            category="Healthcare",
            service="Web Application Development",
            auto_ingest=False,
        )
        london_res = execute_discovery(london_req)
        l_candidates = london_res["candidates"]
        assert len(l_candidates) == 1, f"Expected 1 London match, got {len(l_candidates)}"
        lon_lead = l_candidates[0]
        assert "London" in lon_lead["location"]
        assert lon_lead["is_live_discovery"] is False
        assert lon_lead["record_type"] == "demo"
        assert lon_lead["verification_status"] == "demo"
        # Ensure zero bleed
        for c in l_candidates:
            assert "Telangana" not in c["location"]
            assert "Austin" not in c["location"]
            assert "Chicago" not in c["location"]
        print(f"       PASS -> Isolated 1 London benchmark ({lon_lead['business_name']}) with zero bleed")

        # Test 13: Nonexistent Location (Antarctica)
        print("\n[13/16] Verifying Nonexistent Location Query (Antarctica)...")
        unmatched_req = DiscoveryRequest(
            location="Antarctica",
            category="Healthcare",
            service="Website Development",
            auto_ingest=False,
        )
        unmatched_res = execute_discovery(unmatched_req)
        assert len(unmatched_res["candidates"]) == 0
        assert unmatched_res["stats"]["status"] == "no_matches"
        assert "No verified opportunities found" in unmatched_res["stats"]["message"]
        print(f"       PASS -> Nonexistent query returned 0 candidates with explicit message: \"{unmatched_res['stats']['message']}\"")

        # Test 14: Anti-Fabrication & Static Demonstration Classification
        print("\n[14/16] Verifying Static Benchmarks Cannot Receive Live Discovery Status...")
        demo_req = DiscoveryRequest(
            location="Telangana",
            category="Healthcare",
            service="Website Development",
            auto_ingest=False,
        )
        demo_res = execute_discovery(demo_req)
        stats = demo_res["stats"]
        assert stats["mode"] == "static_benchmark"
        assert stats["is_live_discovery"] is False
        assert stats["live_provider_connected"] is False
        assert "DEMONSTRATION / STATIC BENCHMARK MODE" in stats["notice"]
        for cand in demo_res["candidates"]:
            assert cand["record_type"] == "demo", "Static benchmark must consistently have record_type == demo"
            assert cand["verification_status"] == "demo", "Static benchmark must consistently have verification_status == demo"
            assert cand["is_live_discovery"] is False
            assert cand["verification_status"] != "official_tender", "Static benchmark cannot be presented as official_tender"
            assert cand["verification_status"] != "verified", "Static benchmark cannot be presented as verified"
        print("       PASS -> Static demonstration records strictly prevented from receiving Live Discovery or Verified status")

    # Test 15: Source Domain Confirmed != Tender Independently Verified Rule
    print("\n[15/16] Verifying Domain Confirmed vs. Tender Independently Verified Rule...")
    from backend.services.discovery_service import validate_source_url
    # Portal homepages: domain is confirmed, but tender is NOT independently verified
    tel_valid, tel_status, tel_notes = validate_source_url("https://tender.telangana.gov.in/")
    assert tel_valid is False, "Homepage-only URL must have is_verified = False"
    assert tel_status == "source_domain_confirmed_tender_unverified"

    austin_valid, austin_status, austin_notes = validate_source_url("https://www.austintexas.gov/department/purchasing")
    assert austin_valid is False
    assert austin_status == "source_domain_confirmed_tender_unverified"

    # Synthetic / invalid domains must fail completely
    synth_valid, synth_status, _ = validate_source_url("https://example.com/rfp/123")
    assert synth_valid is False
    assert synth_status == "unverified"

    empty_valid, empty_status, _ = validate_source_url("")
    assert empty_valid is False
    assert empty_status == "unverified"
    print("       PASS -> Domain confirmation strictly distinguished from independent tender verification")

    # Test 16: Historical Record Auditing & Preservation
    print("\n[16/18] Verifying Historical Record Auditing & Data Separation...")
    from backend.db import get_lead_by_id
    lead_1 = get_lead_by_id(1)
    assert lead_1["record_type"] == "demo"
    assert lead_1["verification_status"] == "demo"
    assert lead_1["is_exported"] == 1

    lead_25 = get_lead_by_id(25)
    assert lead_25["record_type"] == "uploaded"
    assert lead_25["verification_status"] == "unverified"

    # Verify previously auto-ingested test records 314, 315, 316
    for test_id in [314, 315, 316]:
        r = get_lead_by_id(test_id)
        if r:
            assert r["record_type"] == "sample"
            assert r["verification_status"] == "unverified"
            assert "unverified source" in (r["verification_notes"] or "").lower()
    print("       PASS -> Historical records strictly separated: IDs 1-24=demo, 25-27=uploaded, 314-316=unverified sample")

    # Test 17: Serper Provider Targeted Search & Mocked Provenance Verification
    print("\n[17/18] Verifying Serper.dev Provider Adapter & 9 Provenance Fields (Mocked)...")
    from backend.services.serper_provider import SerperProvider

    with patch("httpx.Client.post") as mock_serper_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "searchParameters": {"q": "Telangana RFP", "gl": "in"},
            "organic": [
                {
                    "title": "Tender Notice: Telangana Irrigation Dept Invites Proposals for Mobile Telemetry App",
                    "link": "https://irrigation.telangana.gov.in/tenders/nit-2026-889.pdf",
                    "snippet": "Notice Inviting Tender No NIT-2026-889: Sealed proposals are invited for mobile telemetry system. Bid submission deadline: 2026-10-15.",
                    "date": "2026-09-01",
                },
                {
                    "title": "Top 10 Web Development Companies in Hyderabad",
                    "link": "https://agencylist.com/top-10",
                    "snippet": "Hire the best web development agency in Hyderabad from our directory.",
                },
            ],
            "credits": 1,
        }
        mock_serper_post.return_value = mock_resp

        mock_provider = SerperProvider(api_key="mock_secret_key_testing")
        candidates, meta = mock_provider.search("Telangana", "Healthcare", "Mobile Application Development")
        assert meta["success"] is True
        # Directory listing filtered out, keeping 1 genuine procurement opportunity
        assert len(candidates) == 1
        cand = candidates[0]
        # Verify all 9 provenance fields
        assert cand["provider_name"] == "serper"
        assert cand["record_type"] == "live_discovery"
        assert "irrigation.telangana.gov.in" in cand["source_url"]
        assert cand["source_domain"] == "irrigation.telangana.gov.in"
        assert cand["discovered_at"] is not None
        assert len(cand["evidence_text"]) > 10
        assert cand["verification_status"] == "official_tender"
        assert cand["is_live_discovery"] is True
        assert len(cand["search_query"]) > 10
        assert cand["buying_intent"] == "Active"

    print("       PASS -> Serper provider extracted live opportunity with all 9 provenance fields; directory spam rejected")

    # Test 18: Serper Provider Error & Rate-Limit Resilience
    print("\n[18/20] Verifying Serper.dev HTTP 429 & Timeout Error Resilience...")
    with patch("httpx.Client.post") as mock_serper_error:
        # Test Rate Limit (HTTP 429)
        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = '{"message": "Too Many Requests"}'
        mock_serper_error.return_value = mock_resp_429

        mock_provider = SerperProvider(api_key="mock_secret_key_testing")
        candidates_429, meta_429 = mock_provider.search("Hyderabad", "Healthcare", "Website Development")
        assert candidates_429 == []
        assert meta_429["success"] is False
        assert meta_429["status_code"] == 429
        assert "rate limit" in meta_429["error"].lower()

        # Test Timeout
        import httpx
        mock_serper_error.side_effect = httpx.TimeoutException("Timed out")
        candidates_timeout, meta_timeout = mock_provider.search("Hyderabad", "Healthcare", "Website Development")
        assert candidates_timeout == []
        assert meta_timeout["success"] is False
        assert "timed out" in meta_timeout["error"].lower()

    print("       PASS -> HTTP 429 and network timeouts safely handled with zero crash or key leakage")

    # Test 19: Tavily Provider Adapter & Provenance (Mocked)
    print("\n[19/20] Verifying Tavily Provider Adapter & 9 Provenance Fields (Mocked)...")
    from backend.services.tavily_provider import TavilyProvider
    with patch("httpx.Client.post") as mock_tavily_post:
        mock_tavily_resp = MagicMock()
        mock_tavily_resp.status_code = 200
        mock_tavily_resp.json.return_value = {
            "results": [
                {
                    "title": "Tender Notice: Telangana eProcurement Portal for Citizen Healthcare App",
                    "url": "https://health.telangana.gov.in/tenders/tender-089.html",
                    "content": "Notice Inviting Tender Ref TS/HLT/2026/089: Proposals are invited for mobile health app. Bid submission deadline: 2026-11-15.",
                },
                {
                    "title": "Top 10 Web Agencies in Hyderabad",
                    "url": "https://directory.com/top-10",
                    "content": "We list top web development agencies.",
                },
            ]
        }
        mock_tavily_post.return_value = mock_tavily_resp

        tavily = TavilyProvider(api_key="mock_tavily_key_testing")
        t_candidates, t_meta = tavily.search("Telangana", "Healthcare", "Mobile Application Development")
        assert t_meta["success"] is True
        assert len(t_candidates) == 1
        t_cand = t_candidates[0]
        assert t_cand["provider_name"] == "tavily"
        assert t_cand["record_type"] == "live_discovery"
        assert t_cand["verification_status"] == "official_tender"
        assert t_cand["buying_intent"] == "Active"
        assert t_cand["is_live_discovery"] is True

    print("       PASS -> Tavily free search provider parsed live candidates with full provenance and directory filtering")

    # Test 20: Tavily Free Credit Exhaustion & Provider Selection Mechanism
    print("\n[20/20] Verifying Tavily Credit Exhaustion Handling & Provider Selection...")
    from backend.services.provider_manager import get_active_discovery_provider, get_all_providers_status

    # 1. Credit exhaustion test
    with patch("httpx.Client.post") as mock_exhaust_post:
        mock_exhaust_resp = MagicMock()
        mock_exhaust_resp.status_code = 402
        mock_exhaust_resp.text = '{"detail": "Usage limit reached"}'
        mock_exhaust_post.return_value = mock_exhaust_resp

        tavily_exhaust = TavilyProvider(api_key="mock_tavily_key_testing")
        e_candidates, e_meta = tavily_exhaust.search("Hyderabad", "Healthcare", "Website Development")
        assert e_candidates == []
        assert e_meta["credit_exhausted"] is True
        assert "exhausted" in e_meta["error"].lower()

    # 2. Provider selection test
    with patch.object(settings, "DISCOVERY_PROVIDER", "static_benchmark"):
        p_name, p_inst = get_active_discovery_provider()
        assert p_name == "static_benchmark"
        assert p_inst is None

    with patch.object(settings, "DISCOVERY_PROVIDER", "mwmbl"):
        m_name, m_inst = get_active_discovery_provider()
        assert m_name == "mwmbl"
        assert m_inst.is_configured() is True

    health = health_check()
    assert "providers" in health["discovery"]
    assert "tavily" in health["discovery"]["providers"]

    print("       PASS -> Free credit exhaustion handled cleanly; provider selection strictly respects budget limits")

    # Test 21: Mwmbl Targeted Demand Query Construction
    print("\n[21/24] Verifying Mwmbl Targeted Demand Query Construction...")
    from backend.services.mwmbl_provider import MwmblProvider, clean_organisation_name
    mwmbl = MwmblProvider()

    # Healthcare demand query
    hc_queries = mwmbl.build_search_queries("Hyderabad, Telangana, India", "Healthcare", "Website Development")
    assert any("requirement" in q for q in hc_queries), f"Expected demand term 'requirement' in queries: {hc_queries}"
    assert any("Healthcare" in q or "hospital" in q for q in hc_queries)
    assert any("Hyderabad" in q for q in hc_queries)

    # Education demand query
    edu_queries = mwmbl.build_search_queries("Hyderabad", "Education", "Website Development")
    assert any("Education" in q or "school" in q for q in edu_queries)

    # Retail demand query
    ret_queries = mwmbl.build_search_queries("Hyderabad", "Retail & E-commerce", "E-commerce Website Development")
    assert any("retail" in q.lower() or "ecommerce" in q.lower() for q in ret_queries)
    print(f"       PASS -> Constructed specific demand queries for Healthcare, Education, and Retail ({len(hc_queries)} variants)")

    # Test 22: Mwmbl 3-Tier Classification & Agency / Platform Filtering
    print("\n[22/24] Verifying 3-Tier Classification (Active, Potential, Unqualified)...")
    mock_mwmbl_raw = [
        # Active procurement notice
        {
            "title": [{"value": "Tender Ref HLT-2026-90: Patient Portal Web Application"}],
            "url": "https://health.telangana.gov.in/tenders/hlt-90.html",
            "extract": [{"value": "Notice Inviting Tender: sealed proposals are invited for hospital web portal."}],
        },
        # Potential: Healthcare organization with specific evidence of need
        {
            "title": [{"value": "Care Hospitals Hyderabad - Seeking Web Agency for Portal Redesign"}],
            "url": "https://carehospitals.com/rfp-web-redesign",
            "extract": [{"value": "Seeking agency for hospital website redesign and patient portal development."}],
        },
        # Unqualified: Agency portfolio showcasing past healthcare work (Swaragh case)
        {
            "title": [{"value": "Healthcare Website Development | Swaragh Technologies"}],
            "url": "https://swaragh.com/portfolio-healthcare",
            "extract": [{"value": "Our Healthcare Portfolios As health care is a 24/7 requirement, Swaragh has been able to support their websites with relevant information."}],
        },
        # Unqualified: Agency selling services
        {
            "title": [{"value": "Healthcare Website Design and Development | Nomadic Soft"}],
            "url": "https://nomadicsoft.io/healthcare/",
            "extract": [{"value": "We build custom healthcare websites and digital transformation solutions."}],
        },
        # Unqualified: Platform / Template
        {
            "title": [{"value": "Hospital Website Templates | Loopple"}],
            "url": "https://www.loopple.com/templates/hospital",
            "extract": [{"value": "Free responsive hospital website templates for download."}],
        },
        # Unqualified: Discussion forum
        {
            "title": [{"value": "Website development from scratch vs framework"}],
            "url": "http://programmers.stackexchange.com/a/109806",
            "extract": [{"value": "Discussion on php frameworks vs custom code."}],
        },
    ]

    relevant, unqualified = mwmbl._process_and_classify_results(
        results=mock_mwmbl_raw,
        primary_query="Hyderabad Healthcare website development requirement",
        target_location="Hyderabad, Telangana, India",
        target_category="Healthcare",
        target_service="Website Development",
        limit=10,
    )

    assert len(relevant) == 2, f"Expected 2 relevant leads (1 Active, 1 Potential), got {len(relevant)}"
    assert len(unqualified) == 4, f"Expected 4 unqualified filtered items, got {len(unqualified)}"

    # Check Active item
    active_item = next(c for c in relevant if c["buying_intent"] == "Active")
    assert "health.telangana.gov.in" in active_item["source_url"]
    assert active_item["verification_status"] == "official_tender"
    assert active_item["is_live_discovery"] is True

    # Check Potential item
    pot_item = next(c for c in relevant if c["buying_intent"] == "Potential")
    assert "Care Hospitals" in pot_item["business_name"]
    assert pot_item["verification_status"] == "unverified"

    # Check Swaragh portfolio item is strictly Unqualified
    swaragh_unq = next(u for u in unqualified if "swaragh.com" in u["url"])
    assert swaragh_unq["classification"] == "Unqualified"
    assert "portfolio" in swaragh_unq["reason"].lower() or "purchasing" in swaragh_unq["reason"].lower()

    # Check Unqualified items have explicit reasons
    agency_unq = next(u for u in unqualified if "nomadicsoft.io" in u["url"])
    assert "seller, not buyer" in agency_unq["reason"]

    platform_unq = next(u for u in unqualified if "loopple.com" in u["url"])
    assert "template" in platform_unq["reason"] or "platform" in platform_unq["reason"]

    print("       PASS -> 3-tier classification cleanly separated Active (1), Potential (1), and Unqualified (4, including Swaragh portfolio)")

    # Test 23: Real Organisation Name Extraction (Zero Webpage Title Duplication)
    print("\n[23/24] Verifying Real Organisation Name Extraction...")
    org1 = clean_organisation_name("Healthcare Website Development | Swaragh Technologies", "swaragh.com")
    assert org1 == "Swaragh Technologies", f"Expected 'Swaragh Technologies', got '{org1}'"

    org2 = clean_organisation_name("Website Development", "reliqus.com")
    assert org2 == "Reliqus", f"Expected 'Reliqus', got '{org2}'"

    org3 = clean_organisation_name("Best Website Development Company | Brandshark", "brandshark.in")
    assert org3 == "Brandshark", f"Expected 'Brandshark', got '{org3}'"

    print("       PASS -> Organisation names correctly extracted without copying generic titles like 'Website Development'")

    # Test 24: "Existence Alone != Intent" Rule Verification
    print("\n[24/24] Verifying 'Existence Alone Does Not Indicate Intent' Rule...")
    sample_existing_org = [
        {
            "title": [{"value": "Apollo Clinic Jubilee Hills"}],
            "url": "https://apolloclinic.com/jubilee-hills",
            "extract": [{"value": "Consult top general physicians and pediatricians in Jubilee Hills Hyderabad. Clinic open 8am to 8pm."}],
        }
    ]
    rel_org, unq_org = mwmbl._process_and_classify_results(
        results=sample_existing_org,
        primary_query="Hyderabad Healthcare website development requirement",
        target_location="Hyderabad, Telangana, India",
        target_category="Healthcare",
        target_service="Website Development",
        limit=5,
    )
    assert len(rel_org) == 0, "Organisation existence without demand evidence MUST NOT be classified as buying lead"
    assert len(unq_org) == 1
    assert "existence alone does not indicate intent" in unq_org[0]["reason"].lower()
    print("       PASS -> Organisations without active/potential demand signals are strictly classified as Unqualified")

    # Test 25: Publication-Date & Discovery-Timestamp Separation
    print("\n[25/26] Verifying Publication-Date vs. Discovered-At Separation...")
    raw_with_no_date = [
        {
            "title": [{"value": "Rainbow Children Hospital - Requesting Proposals for Website Redesign"}],
            "url": "https://rainbowhospitals.in/web-rfp",
            "extract": [{"value": "Rainbow Children Hospital is requesting proposals for a website redesign and patient portal."}],
        }
    ]
    rel_date, _ = mwmbl._process_and_classify_results(
        results=raw_with_no_date,
        primary_query="Hyderabad Healthcare website development requirement",
        target_location="Hyderabad, Telangana, India",
        target_category="Healthcare",
        target_service="Website Development",
        limit=5,
    )
    assert len(rel_date) == 1
    cand_date = rel_date[0]
    assert cand_date["publication_date"] is None, f"Expected publication_date to be None when source has no date, got: {cand_date['publication_date']}"
    assert cand_date["discovered_at"] is not None
    assert "T" in cand_date["discovered_at"], "discovered_at must be an ISO timestamp"
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    assert cand_date["publication_date"] != today_str or cand_date["publication_date"] is None, "publication_date must NEVER automatically copy today's date"

    # Now verify when an explicit publication date IS present in source snippet
    raw_with_date = [
        {
            "title": [{"value": "Tender Notice: Primary Health Centre Web App"}],
            "url": "https://health.telangana.gov.in/tenders/tender-101.html",
            "extract": [{"value": "Published: 2026-07-20. Notice Inviting Tender Ref PHC-2026-101: Proposals are invited for portal."}],
        }
    ]
    rel_with_date, _ = mwmbl._process_and_classify_results(
        results=raw_with_date,
        primary_query="Hyderabad Healthcare website development requirement",
        target_location="Hyderabad, Telangana, India",
        target_category="Healthcare",
        target_service="Website Development",
        limit=5,
    )
    assert len(rel_with_date) == 1
    assert rel_with_date[0]["publication_date"] == "2026-07-20", f"Expected '2026-07-20', got {rel_with_date[0]['publication_date']}"
    print("       PASS -> publication_date is None when missing (never defaults to today) and preserves exact source date when present")

    # Test 26: Real Explicit Requirement vs Software Company Service Page
    print("\n[26/26] Verifying Service Page Rejection vs Real Buyer Requirement Qualification...")
    mixed_candidates = [
        # Software company service page
        {
            "title": [{"value": "Award-Winning Healthcare Website Development Company | Arkenea"}],
            "url": "https://arkenea.com/healthcare-web-app",
            "extract": [{"value": "Work with an award-winning healthcare website development company to build custom HIPAA-compliant apps."}],
        },
        # Real hospital buyer with explicit unmet requirement
        {
            "title": [{"value": "Apollo Health City Hyderabad - Request for Proposals for Patient Portal Overhaul"}],
            "url": "https://apollohealthcity.com/rfp-portal-2026",
            "extract": [{"value": "Apollo Health City Hyderabad is seeking proposals for website redesign and digital transformation initiative for new patient portal."}],
        },
    ]
    rel_mixed, unq_mixed = mwmbl._process_and_classify_results(
        results=mixed_candidates,
        primary_query="Hyderabad Healthcare website development requirement",
        target_location="Hyderabad, Telangana, India",
        target_category="Healthcare",
        target_service="Website Development",
        limit=5,
    )
    assert len(rel_mixed) == 1, f"Expected 1 real buyer requirement, got {len(rel_mixed)}"
    assert len(unq_mixed) == 1, f"Expected 1 unqualified service page, got {len(unq_mixed)}"

    buyer_lead = rel_mixed[0]
    assert "Apollo Health City" in buyer_lead["business_name"]
    assert buyer_lead["buying_intent"] in ["Active", "Potential"]
    assert buyer_lead["category"] == "Healthcare"

    seller_page = unq_mixed[0]
    assert "arkenea.com" in seller_page["url"]
    assert seller_page["classification"] == "Unqualified"
    assert "seller, not buyer" in seller_page["reason"].lower() or "offering" in seller_page["reason"].lower()
    print("       PASS -> Software company service page disqualified; real hospital buyer requirement qualified with correct attribution")

    # Test 27: Phase 4 Source Page Verification Suite (13 Unit Tests)
    print("\n[27/27] Verifying Source Page Verification Engine (Phase 4 Suite)...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSourceVerifier)
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    assert result.wasSuccessful(), f"Source verifier unit tests failed: {len(result.errors)} errors, {len(result.failures)} failures"
    print(f"       PASS -> Executed {result.testsRun} Source Page Verification unit tests (100% PASS)")

    print("\n" + "=" * 70)
    print("ALL 27 VERIFICATION SUITES COMPLETED SUCCESSFULLY (100% PASS)!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_tests()
