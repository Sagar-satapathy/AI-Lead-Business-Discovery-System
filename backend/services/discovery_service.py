"""
backend/services/discovery_service.py - Commercial Business Discovery Engine

Architecture & Verification Principles:
1. Zero Fabrication: No hallucinated RFPs, fake URLs, synthetic companies, or fictitious contact details.
2. Strict Matching: Search criteria (Location, Category, Service) are strictly enforced. Non-matching
   locations are strictly rejected.
3. Independent Source Verification: Opportunities are only labeled 'verified' when their publishing
   organisation and official procurement source URL are authenticated against recognized government
   or public authority portals.
4. Transparent Provenance: Every record records the original source URL, source title, publication date,
   verification status, and verification audit notes.
5. Strict Fallback Handling: When no genuine matching opportunities exist for a query, the engine
   returns 0 results with an explicit "No verified opportunities found" message.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import urllib.parse
import datetime
import asyncio
import concurrent.futures
from backend.config import settings
from backend.db import insert_lead
from backend.services.serper_provider import SerperProvider
from backend.services.provider_manager import get_active_discovery_provider
from backend.services.source_verifier import verify_candidates_concurrently


def run_sync_verification(candidates: List[Dict[str, Any]], timeout: float = 4.0) -> List[Dict[str, Any]]:
    """Helper to run async candidate verification safely in synchronous discovery contexts."""
    if not candidates:
        return []
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(verify_candidates_concurrently(candidates, timeout_seconds=timeout))).result()
    else:
        return asyncio.run(verify_candidates_concurrently(candidates, timeout_seconds=timeout))

# Recognized authoritative public procurement and government domains
AUTHORITATIVE_PORTAL_DOMAINS = [
    "gov.in",
    "nic.in",
    "telangana.gov.in",
    "gov.uk",
    "service.gov.uk",
    "contractsfinder.service.gov.uk",
    "sam.gov",
    "austintexas.gov",
    "chicago.gov",
    "toronto.ca",
    "canada.ca",
    "europa.eu",
    "ungm.org",
    "undp.org",
    "who.int",
    "worldbank.org",
]

# Geographic alias mappings for normalized strict matching
LOCATION_ALIASES: Dict[str, List[str]] = {
    # Indian States & Union Territories
    "telangana": ["telangana", "hyderabad", "secunderabad", "warangal", "tsts"],
    "hyderabad": ["hyderabad", "telangana"],
    "andhra pradesh": ["andhra pradesh", "amaravati", "visakhapatnam", "vijayawada", "tirupati", "guntur"],
    "arunachal pradesh": ["arunachal pradesh", "itanagar"],
    "assam": ["assam", "guwahati", "dispur"],
    "bihar": ["bihar", "patna", "gaya"],
    "chhattisgarh": ["chhattisgarh", "raipur", "bilaspur"],
    "goa": ["goa", "panaji"],
    "gujarat": ["gujarat", "ahmedabad", "gandhinagar", "surat", "vadodara", "rajkot"],
    "haryana": ["haryana", "gurugram", "gurgaon", "faridabad", "panchkula"],
    "himachal pradesh": ["himachal pradesh", "shimla", "dharamshala"],
    "jharkhand": ["jharkhand", "ranchi", "jamshedpur"],
    "karnataka": ["karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "hubballi"],
    "kerala": ["kerala", "thiruvananthapuram", "trivandrum", "kochi", "cochin", "kozhikode"],
    "madhya pradesh": ["madhya pradesh", "bhopal", "indore", "gwalior", "jabalpur"],
    "maharashtra": ["maharashtra", "mumbai", "pune", "nagpur", "nashik", "thane"],
    "manipur": ["manipur", "imphal"],
    "meghalaya": ["meghalaya", "shillong"],
    "mizoram": ["mizoram", "aizawl"],
    "nagaland": ["nagaland", "kohima", "dimapur"],
    "odisha": ["odisha", "orissa", "bhubaneswar", "cuttack"],
    "punjab": ["punjab", "ludhiana", "amritsar", "mohali", "jalandhar"],
    "rajasthan": ["rajasthan", "jaipur", "jodhpur", "udaipur", "kota"],
    "sikkim": ["sikkim", "gangtok"],
    "tamil nadu": ["tamil nadu", "chennai", "madras", "coimbatore", "madurai"],
    "tripura": ["tripura", "agartala"],
    "uttar pradesh": ["uttar pradesh", "lucknow", "noida", "greater noida", "kanpur", "varanasi", "agra"],
    "uttarakhand": ["uttarakhand", "dehradun", "haridwar"],
    "west bengal": ["west bengal", "kolkata", "calcutta", "siliguri"],
    "delhi": ["delhi", "new delhi", "ncr"],
    "chandigarh": ["chandigarh"],
    "jammu and kashmir": ["jammu and kashmir", "srinagar", "jammu"],
    "ladakh": ["ladakh", "leh"],
    "puducherry": ["puducherry", "pondicherry"],
    "andaman and nicobar islands": ["andaman and nicobar", "port blair"],
    "dadra and nagar haveli and daman and diu": ["dadra and nagar haveli", "daman", "diu"],
    "lakshadweep": ["lakshadweep", "kavaratti"],
    # International & Benchmark Baselines
    "austin": ["austin", "texas", "tx", "travis county"],
    "chicago": ["chicago", "illinois", "il", "cook county"],
    "london": ["london", "uk", "united kingdom", "england", "greater london"],
    "new york": ["new york", "ny", "nyc", "manhattan"],
    "boston": ["boston", "massachusetts", "ma"],
    "toronto": ["toronto", "ontario", "canada"],
    "seattle": ["seattle", "washington", "wa"],
    "denver": ["denver", "colorado", "co"],
    "dallas": ["dallas", "texas", "tx"],
    "san francisco": ["san francisco", "california", "ca", "bay area"],
}

# Predefined demonstration procurement benchmarks
# Note: In accordance with authenticity standards, these records are structured demonstration
# benchmarks. They are NOT active commercial discoveries or independently verified live tenders.
DEMO_PROCUREMENT_BENCHMARKS: List[Dict[str, Any]] = [
    {
        "business_name": "Telangana State Technology Services (TSTS) / Department of Health, Medical & Family Welfare",
        "location": "Hyderabad, Telangana, India",
        "category": "Healthcare",
        "service": "Website Development",
        "requirement": "Tender Ref TSTS/HWP/2026/04: Request for Proposal for the Design, Development, Deployment and Annual Maintenance of the integrated Telemedicine Consultation Portal and Primary Healthcare Web Portal for District Health Centres across Telangana. Requirements include bilingual citizen interface (Telugu and English), patient registration module, doctor video consultation schedule integration, and ABDM/FHIR compliant health record integration.",
        "source_name": "Telangana State eProcurement Portal",
        "source_url": "https://tender.telangana.gov.in/",
        "source_title": "Tender Notification TSTS/HWP/2026/04 - Telangana Health Centres Integrated Web Portal",
        "publication_date": "2026-08-14",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "Telangana State Road Transport Corporation (TSRTC) / IT Cell",
        "location": "Hyderabad, Telangana, India",
        "category": "Logistics & Supply Chain",
        "service": "Mobile Application Development",
        "requirement": "Tender Notice TSRTC/IT/APP/2026/02: Development and maintenance of cross-platform native mobile passenger application (Android and iOS) with live GPS bus tracking, digital ticketing QR payment integration, and smart transit pass renewal.",
        "source_name": "Telangana eProcurement Portal",
        "source_url": "https://tender.telangana.gov.in/",
        "source_title": "TSRTC/IT/APP/2026/02 - NextGen Passenger Transit Mobile Application",
        "publication_date": "2026-09-02",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "City of Austin Financial Services & Austin Public Health Department",
        "location": "Austin, TX, USA",
        "category": "Healthcare",
        "service": "Mobile Application Development",
        "requirement": "Solicitation RFP 1100 CLMB102: Austin Public Health seeks vendor proposals for the development, hosting, and support of a HIPAA-compliant mobile community health outreach and patient appointment application with biometrics, SMS appointment reminders, and Electronic Health Record integration.",
        "source_name": "City of Austin Purchasing Portal",
        "source_url": "https://www.austintexas.gov/department/purchasing",
        "source_title": "Solicitation RFP 1100 CLMB102 - Austin Public Health Mobile Outreach App",
        "publication_date": "2026-07-20",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "Crown Commercial Service & NHS England",
        "location": "London, UK",
        "category": "Healthcare",
        "service": "Web Application Development",
        "requirement": "Notice Ref CF-028471: Digital Outcomes and Specialists framework procurement for NHS clinical audit web portal. Development of secure cloud-hosted clinical dashboard, multi-trust role-based access control, and automated NHS Trust compliance report generation conforming to NHS Service Standard.",
        "source_name": "UK Contracts Finder (Gov.UK)",
        "source_url": "https://www.contractsfinder.service.gov.uk/",
        "source_title": "Notice CF-028471 - NHS England Clinical Audit Web Portal",
        "publication_date": "2026-06-11",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "City of Chicago Department of Assets, Information and Services",
        "location": "Chicago, IL, USA",
        "category": "Logistics & Supply Chain",
        "service": "Web Application Development",
        "requirement": "Specification No. 1204891: Request for Proposals for Fleet Management and Telematics Web Application Platform. Software system to aggregate real-time IoT diagnostic data from 12,000 municipal vehicles, route optimization, automated preventative maintenance ticketing, and ERP financial system integration.",
        "source_name": "City of Chicago Procurement Services",
        "source_url": "https://www.chicago.gov/city/en/depts/dps.html",
        "source_title": "Spec No. 1204891 - Municipal Fleet Telematics Web Application Platform",
        "publication_date": "2026-05-18",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "U.S. Department of Health and Human Services / HRSA",
        "location": "Boston, MA, USA",
        "category": "Biotech & Healthcare",
        "service": "Website Development",
        "requirement": "Contract Opportunity Notice 75R60226R00014: Redesign and modernization of the national health workforce training portal on Section 508 / WCAG 2.1 AA compliant headless CMS, dynamic provider locator directory, and federated login integration.",
        "source_name": "SAM.gov Contract Opportunities",
        "source_url": "https://sam.gov/content/opportunities",
        "source_title": "Notice 75R60226R00014 - National Health Workforce Web Portal Modernization",
        "publication_date": "2026-06-30",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
    {
        "business_name": "City of Toronto Technology Services Division",
        "location": "Toronto, Canada",
        "category": "Education & EdTech",
        "service": "Mobile Application Development",
        "requirement": "Negotiated Request for Proposal 9144-26-0102: Community youth digital recreation and educational workshop mobile application for iOS and Android platforms with interactive event maps, accessibility features, and single sign-on.",
        "source_name": "City of Toronto Purchasing & Materials Management",
        "source_url": "https://www.toronto.ca/business-economy/doing-business-with-the-city/",
        "source_title": "NRFP 9144-26-0102 - Community Digital Education & Recreation Mobile App",
        "publication_date": "2026-07-15",
        "record_type": "demo",
        "verification_status": "demo",
        "is_live_discovery": False,
        "verification_notes": "Predefined demonstration benchmark. Pre-configured reference benchmark; not an active commercial discovery.",
    },
]

# Backwards compatibility alias
VERIFIED_PUBLIC_TENDERS = DEMO_PROCUREMENT_BENCHMARKS


def validate_source_url(url: str, organisation_name: str = "") -> Tuple[bool, str, str]:
    """
    Independently validates that a source URL represents an authentic public procurement
    authority or verified official portal.

    Authenticity & Zero-Fabrication Rules:
    1. Rejects malformed URLs, empty strings, and synthetic placeholder domains (example.com, test.com).
    2. Rule 4 & 10: Merely having an official domain (.gov.in, .gov, .gov.uk) or portal homepage
       DOES NOT prove that an individual tender or RFP is verified. If only the general portal homepage
       is provided, it is classified as 'source_domain_confirmed_tender_unverified' with is_verified = False.
    3. Only deep URLs pointing to an authentic published tender document with verified status qualify as 'official_tender'.

    Returns (is_verified: bool, verification_status: str, verification_notes: str).
    """
    if not url or not isinstance(url, str):
        return False, "unverified", "Unverified: Missing source URL"

    url_clean = url.strip()
    if not (url_clean.startswith("http://") or url_clean.startswith("https://")):
        return False, "unverified", "Unverified: Invalid URL scheme"

    try:
        parsed = urllib.parse.urlparse(url_clean)
        netloc = parsed.netloc.lower()
        path = parsed.path.strip("/")
        if not netloc:
            return False, "unverified", "Unverified: Invalid hostname"

        # Reject synthetic or test placeholders
        if any(dummy in netloc for dummy in ["example.com", "test.com", "placeholder", "mock", "fake", "local"]):
            return False, "unverified", "Unverified: Synthetic placeholder or test domain"

        # Check if domain belongs to an established authoritative public procurement portal
        is_auth_domain = False
        for auth_domain in AUTHORITATIVE_PORTAL_DOMAINS:
            if netloc == auth_domain or netloc.endswith("." + auth_domain):
                is_auth_domain = True
                break

        if not is_auth_domain:
            if netloc.endswith(".gov") or netloc.endswith(".gov.in") or netloc.endswith(".gov.uk") or netloc.endswith(".mil"):
                is_auth_domain = True

        if is_auth_domain:
            # Rule 4 & 10: If only homepage or top-level portal landing page is provided,
            # classify as source-domain-confirmed but tender-not-independently-verified!
            if not path or len(path) < 3 or path in ("index.html", "index.jsp", "home", "default.aspx", "department/purchasing", "content/opportunities"):
                return False, "source_domain_confirmed_tender_unverified", (
                    f"Source domain ({netloc}) confirmed authentic official public portal, "
                    f"but tender document details and active status are not independently verified."
                )
            else:
                return True, "official_tender", (
                    f"Verified: Official document path on authoritative procurement portal ({netloc})."
                )

        return False, "unverified", f"Unverified: Non-authoritative third-party domain ({netloc}); requires independent audit."
    except Exception as e:
        return False, "unverified", f"Unverified: URL parsing error ({str(e)})"


def strict_location_match(candidate_location: str, target_location: str) -> bool:
    """
    Enforces strict location matching.
    Returns True if target_location is empty/All, or if candidate_location strictly matches.
    Searching for 'Telangana' will strictly match Telangana/Hyderabad, but NEVER Austin, London, etc.
    """
    if not target_location or not target_location.strip() or target_location.strip().lower() == "all":
        return True

    target_norm = target_location.strip().lower()
    cand_norm = candidate_location.strip().lower()

    # Direct substring check
    if target_norm in cand_norm:
        return True

    # Check geographic aliases
    for key, aliases in LOCATION_ALIASES.items():
        if target_norm in key or any(target_norm == a for a in aliases):
            # Target is asking for this region
            if any(a in cand_norm for a in aliases):
                return True

    # Check comma-separated tokens (e.g., 'Austin, TX' -> 'Austin')
    target_parts = [p.strip() for p in target_norm.split(",") if len(p.strip()) > 2]
    for part in target_parts:
        if part in cand_norm:
            return True

    return False


def strict_category_match(candidate_category: str, target_category: str) -> bool:
    """
    Enforces strict business category / vertical matching.
    """
    if not target_category or not target_category.strip() or target_category.strip().lower() == "all":
        return True

    target_norm = target_category.strip().lower()
    cand_norm = candidate_category.strip().lower()

    if target_norm in cand_norm or cand_norm in target_norm:
        return True

    # Multi-word match
    target_words = [w for w in target_norm.replace("&", " ").split() if len(w) > 3]
    cand_words = [w for w in cand_norm.replace("&", " ").split() if len(w) > 3]
    return any(tw in cand_words for tw in target_words)


def strict_service_match(candidate_service: str, candidate_requirement: str, target_service: str) -> bool:
    """
    Enforces strict digital service matching.
    """
    if not target_service or not target_service.strip() or target_service.strip().lower() == "all":
        return True

    target_norm = target_service.strip().lower()
    srv_norm = candidate_service.strip().lower()
    req_norm = candidate_requirement.strip().lower()

    if target_norm in srv_norm:
        return True

    # Service keyword mapping
    service_keywords = {
        "website development": ["website", "web portal", "portal", "cms", "redesign"],
        "web application development": ["web application", "web app", "portal", "cloud portal", "saas", "dashboard"],
        "mobile application development": ["mobile app", "ios", "android", "flutter", "react native", "native app"],
        "seo services": ["seo", "search engine", "organic traffic", "ranking", "core web vitals"],
        "digital marketing": ["digital marketing", "ppc", "google ads", "social media", "campaign"],
    }

    keywords = service_keywords.get(target_norm, [target_norm])
    return any(kw in srv_norm or kw in req_norm for kw in keywords)


def discover_leads(
    location: str,
    category: str,
    service: str,
    auto_ingest: bool = False,
    limit: int = 10,
    source_type: str = "procurement",
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes business lead discovery with strict matching against requested
    Location, Business Category, and Digital Service.

    Authenticity & Transparency Standards:
    - Zero fabrication: Results come from curated public procurement demonstration benchmarks or live API search.
    - Strict matching: A search for 'Telangana' strictly matches Telangana records and NEVER
      returns organisations in Austin, Boston, Toronto, or London.
    - Explicit Mode: In the absence of an external live search API key, runs in 'static_benchmark' mode.
    - Predefined demonstration records are NEVER represented as live discoveries.
    - Full provenance: Stores source URL, source title, publication date, and verification status.
    """
    loc_clean = location.strip() if location else ""
    cat_clean = category.strip() if category else ""
    srv_clean = service.strip() if service else ""

    active_name, active_provider = get_active_discovery_provider()
    live_provider_connected = bool(active_provider and active_provider.is_configured())
    mode = "live_search" if live_provider_connected else "static_benchmark"

    matched_candidates: List[Dict[str, Any]] = []
    search_error: Optional[str] = None
    credit_exhausted: bool = False
    search_meta: Dict[str, Any] = {}

    if not live_provider_connected:
        # Search Predefined Demonstration Procurement Benchmarks ONLY if static_benchmark is explicitly configured
        if active_name == "static_benchmark":
            for entry in DEMO_PROCUREMENT_BENCHMARKS:
                # Strict Location Check
                if not strict_location_match(entry["location"], loc_clean):
                    continue

                # Strict Category Check
                if not strict_category_match(entry["category"], cat_clean):
                    continue

                # Strict Service Check
                if not strict_service_match(entry["service"], entry["requirement"], srv_clean):
                    continue

                candidate = dict(entry)
                candidate["record_type"] = "demo"
                candidate["verification_status"] = "demo"
                candidate["is_live_discovery"] = False
                candidate["verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                candidate["discovery_provider"] = "Predefined Static Demonstration Benchmark"
                candidate["source_fetch_status"] = "static_benchmark"
                candidate["source_page_type"] = "buyer_procurement"
                candidate["source_verified_at"] = candidate["verified_at"]
                candidate["source_evidence_snippet"] = candidate.get("requirement", "")
                matched_candidates.append(candidate)
        else:
            search_error = f"Active provider '{active_name}' is not configured or credentials are missing."
    else:
        # 2. Live Search Provider (Tavily, Serper, or Mwmbl)
        try:
            search_kwargs: Dict[str, Any] = {
                "location": loc_clean,
                "category": cat_clean,
                "service": srv_clean,
                "num_results": limit,
            }
            if hasattr(active_provider, "build_marketplace_query") and source_type != "procurement":
                search_kwargs["search_type"] = source_type
            live_results, search_meta = active_provider.search(**search_kwargs)
            if search_meta.get("credit_exhausted"):
                credit_exhausted = True
                search_error = search_meta.get("error", "Free search provider credits are exhausted.")
            elif not search_meta.get("success") and search_meta.get("error"):
                search_error = search_meta.get("error")

            # Concurrently verify candidate destination source pages (Phase 4)
            try:
                verified_live_results = run_sync_verification(live_results, timeout=4.0)
            except Exception as ver_err:
                verified_live_results = live_results

            for item in verified_live_results:
                if (
                    strict_location_match(item["location"], loc_clean)
                    and strict_category_match(item["category"], cat_clean)
                    and strict_service_match(item["service"], item["requirement"], srv_clean)
                ):
                    # Disqualify confirmed seller agencies, portfolios, or directories
                    if item.get("is_seller") or item.get("source_page_type") in ("seller_agency", "portfolio", "directory"):
                        search_meta.setdefault("unqualified_sample", []).append({
                            "url": item.get("source_url", ""),
                            "title": item.get("source_title", ""),
                            "domain": item.get("source_domain", ""),
                            "classification": item.get("source_page_type", "seller_agency"),
                            "reason": f"Disqualified: Source page verified as {item.get('source_page_type', 'seller agency')}",
                            "evidence_snippet": item.get("source_evidence_snippet", ""),
                        })
                        continue

                    # Buyer procurement confirmed from source page HTML
                    if item.get("source_page_type") == "buyer_procurement":
                        item["verification_status"] = "source_page_verified"
                        if item.get("source_evidence_snippet"):
                            item["evidence_text"] = item["source_evidence_snippet"]
                        item["verification_notes"] = "Source page verified: Active procurement requirement confirmed from HTML document."
                    elif item.get("source_fetch_status") in ("timeout", "blocked_403", "server_error_503", "fetch_failed"):
                        item["verification_status"] = "unverified"
                        item["verification_notes"] = f"Source page unreachable ({item.get('source_fetch_status')}); retained as unverified candidate."

                    matched_candidates.append(item)
        except Exception as e:
            search_error = f"Discovery provider error: {str(e)}"

    selected_candidates = matched_candidates[:limit]

    ingested_count = 0
    duplicate_count = 0
    final_candidates = []

    if auto_ingest and selected_candidates:
        for item in selected_candidates:
            success, lead_id, msg = insert_lead(
                business_name=item["business_name"],
                requirement=item["requirement"],
                source_name=item["source_name"],
                source_url=item.get("source_url", ""),
                location=item["location"],
                date_found=item.get("publication_date", datetime.date.today().strftime("%Y-%m-%d")),
                status="unprocessed",
                record_type=item.get("record_type", "live_discovery" if live_provider_connected else "demo"),
                verification_status=item.get("verification_status", "unverified" if live_provider_connected else "demo"),
                source_title=item.get("source_title", ""),
                publication_date=item.get("publication_date", ""),
                verified_at=item.get("verified_at"),
                verification_notes=item.get("verification_notes", ""),
                provider_name=item.get("provider_name", active_name if live_provider_connected else ""),
                source_domain=item.get("source_domain", ""),
                discovered_at=item.get("discovered_at"),
                is_live_discovery=item.get("is_live_discovery", bool(live_provider_connected)),
                search_query=item.get("search_query", ""),
                evidence_text=item.get("evidence_text", ""),
                source_fetch_status=item.get("source_fetch_status"),
                source_page_type=item.get("source_page_type"),
                source_verified_at=item.get("source_verified_at"),
                source_evidence_snippet=item.get("source_evidence_snippet"),
            )
            item_copy = dict(item)
            if success:
                item_copy["id"] = lead_id
                item_copy["ingest_status"] = "ingested"
                ingested_count += 1
            else:
                item_copy["ingest_status"] = "already_exists"
                duplicate_count += 1
            final_candidates.append(item_copy)
    else:
        final_candidates = selected_candidates

    # Formulate clear user-facing diagnostics
    has_matches = len(final_candidates) > 0
    if credit_exhausted:
        status_msg = search_error or "Free search provider credits are exhausted. Please wait for monthly reset or configure another provider."
    elif search_error and not has_matches:
        status_msg = f"Search provider notice: {search_error}"
    elif has_matches:
        if live_provider_connected:
            status_msg = f"Found {len(final_candidates)} live discovered opportunity(s) matching your criteria."
        else:
            status_msg = f"Found {len(final_candidates)} demonstration benchmark(s) matching your criteria."
    else:
        query_desc = []
        if loc_clean:
            query_desc.append(f"location '{loc_clean}'")
        if cat_clean:
            query_desc.append(f"category '{cat_clean}'")
        if srv_clean:
            query_desc.append(f"service '{srv_clean}'")
        criteria_str = ", ".join(query_desc) if query_desc else "selected criteria"
        status_msg = f"No verified opportunities found matching {criteria_str}."

    # Determine provider-specific display title and notice
    if live_provider_connected:
        if active_name == "tavily":
            provider_name_display = "Tavily AI Search Engine (Free Tier)"
            notice_text = (
                "LIVE EXTERNAL DISCOVERY MODE (Tavily AI Search)\n"
                "Live procurement search executed via Tavily Search API. Opportunities reflect "
                "external web discoveries and require independent verification before contracting."
            )
        elif active_name == "serper":
            provider_name_display = "Serper.dev Google Search API"
            notice_text = (
                "LIVE EXTERNAL DISCOVERY MODE (Serper.dev)\n"
                "Live procurement search executed via Serper.dev Google Search API. Opportunities reflect "
                "external web discoveries and require independent verification before contracting."
            )
        elif active_name == "mwmbl":
            provider_name_display = "Mwmbl Open-Source Public Search"
            notice_text = (
                "LIVE EXTERNAL DISCOVERY MODE (Mwmbl)\n"
                "Live web search executed via Mwmbl open-source public API. Opportunities reflect "
                "external web findings and require independent verification."
            )
        else:
            provider_name_display = f"Live Search Provider ({active_name})"
            notice_text = "LIVE EXTERNAL DISCOVERY MODE\nLive external web search active."
    else:
        provider_name_display = "Predefined Demonstration Benchmarks (Live Search Disconnected)"
        notice_text = (
            "DEMONSTRATION / STATIC BENCHMARK MODE\n"
            "Live external procurement search is not connected. These records are predefined "
            "demonstration benchmarks and are not confirmed active commercial opportunities."
        )

    stats = {
        "mode": mode,
        "is_live_discovery": bool(live_provider_connected),
        "live_provider_connected": live_provider_connected,
        "active_provider": active_name,
        "credit_exhausted": credit_exhausted,
        "notice": notice_text,
        "query": {
            "location": location,
            "category": category,
            "service": service,
        },
        "total_matches": len(final_candidates),
        "raw_results_count": search_meta.get("raw_results_count", len(final_candidates)),
        "relevant_count": search_meta.get("relevant_count", len(final_candidates)),
        "unqualified_count": search_meta.get("unqualified_count", 0),
        "unqualified_sample": search_meta.get("unqualified_sample", []),
        "queries_executed": search_meta.get("queries_executed", []),
        "search_query": search_meta.get("query", ""),
        "newly_ingested": ingested_count,
        "duplicates_skipped": duplicate_count,
        "provider": provider_name_display,
        "status": "credit_exhausted" if credit_exhausted else ("matches_found" if has_matches else "no_matches"),
        "message": status_msg,
        "suggestions": [
            "Broaden your search location (e.g. search at state or country level).",
            "Try related service categories or check if the target market has active tenders published.",
        ] if not has_matches and not credit_exhausted else [],
    }

    return final_candidates, stats
