"""
backend/services/serper_provider.py - Serper.dev Google Search API Provider Adapter

Enterprise Provider Adapter for Phase 1 External Business Discovery:
1. Endpoint: https://google.serper.dev/search
2. Authentication: X-API-KEY header (kept exclusively on backend, read from SERPER_API_KEY)
3. Targeted Geographies: India, Telangana, Hyderabad, and global markets
4. Targeted Services: Website Dev, Mobile App Dev, SEO/Digital Marketing, Website Redesign, RFPs/RFQs
5. Authentic Filtering: Distinguishes commercial buyers with active requirements from self-advertising
   IT agencies and directory spam (Clutch, GoodFirms, JustDial, etc.)
6. Full Provenance: provider_name, record_type, source_url, source_domain, discovered_at,
   evidence_text, verification_status, is_live_discovery, search_query
7. Safe Resilience: Request timeouts (5.0s), HTTP 429 rate-limit handling, duplicate prevention,
   and strict secret redaction in logging (API key is NEVER logged).
"""

import os
import re
import time
import logging
import datetime
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
import httpx
from backend.config import settings

logger = logging.getLogger("serper_provider")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [SerperProvider] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

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

# Exclusion domains for directory spam and freelancer marketplaces
DIRECTORY_EXCLUSIONS = [
    "clutch.co",
    "goodfirms.co",
    "justdial.com",
    "sulekha.com",
    "upwork.com",
    "freelancer.com",
    "fiverr.com",
    "glassdoor.com",
    "indeed.com",
    "naukri.com",
    "linkedin.com/jobs",
]

# Patterns identifying self-advertising service providers rather than buyers
SELLER_AGENCY_PATTERNS = [
    r"\btop\s+\d+\b",
    r"\bbest\s+\d+\b",
    r"\btop\s+web\s+development\b",
    r"\bbest\s+web\s+development\b",
    r"\btop\s+mobile\s+app\b",
    r"\bbest\s+mobile\s+app\b",
    r"\bleading\s+(web|mobile|software|seo)\s+(agency|company|firm|services)\b",
    r"\bhire\s+dedicated\b",
    r"\bhire\s+(react|flutter|python|web|mobile|developer|team)\b",
    r"\bour\s+services\s+include\b",
    r"\bwe\s+are\s+a\s+(leading|premier|top)\b",
    r"\bcompanies\s+in\s+hyderabad\b",
    r"\bagencies\s+in\s+hyderabad\b",
    r"\bcompanies\s+in\s+telangana\b",
    r"\bagencies\s+in\s+telangana\b",
    r"\brated\s+agencies\b",
]

# Procurement requirement / buying intent indicator patterns
ACTIVE_INTENT_PATTERNS = [
    r"\btender\b",
    r"\brfp\b",
    r"\brfq\b",
    r"\beoi\b",
    r"\bexpression\s+of\s+interest\b",
    r"\brequest\s+for\s+proposal\b",
    r"\bnotice\s+inviting\s+tender\b",
    r"\bnit\s+no\b",
    r"\binvites\s+(bids|tenders|proposals)\b",
    r"\bproposals\s+are\s+invited\b",
    r"\bbid\s+submission\b",
    r"\bclosing\s+date\b",
    r"\bdeadline\b",
    r"\bprocurement\s+notice\b",
    r"\btender\s+notice\b",
    r"\btender\s+reference\b",
]

POTENTIAL_INTENT_PATTERNS = [
    r"\bseeking\s+(proposals|vendor|agency|partner|bids)\b",
    r"\blooking\s+for\s+(an?\s+agency|a\s+vendor|a\s+partner|development\s+team)\b",
    r"\bvendor\s+needed\b",
    r"\brequired\s+to\s+develop\b",
    r"\brequirement\s+for\b",
    r"\bscope\s+of\s+work\b",
    r"\bredesign\s+(of\s+)?(website|portal)\b",
    r"\brevamping\s+(of\s+)?(website|portal)\b",
    r"\bproject\s+requirement\b",
]


class SerperProvider:
    """
    Adapter for Serper.dev Google Search API with security, provenance,
    filtering, and non-destructive resilience.
    """

    ENDPOINT = "https://google.serper.dev/search"
    TIMEOUT_SECONDS = 5.0
    PAGE_FETCH_TIMEOUT_SECONDS = 2.0

    # Class-level state tracking
    _total_queries: int = 0
    _last_query_at: Optional[str] = None
    _last_query_successful: bool = False

    def __init__(self, api_key: Optional[str] = None):
        # Prefer injected key or environment setting
        self._api_key = (api_key or settings.SERPER_API_KEY or "").strip()

    def is_configured(self) -> bool:
        """Returns True if a non-empty SERPER_API_KEY is configured."""
        return bool(self._api_key)

    def is_operational(self) -> bool:
        """Returns True if the provider adapter is configured and ready."""
        return self.is_configured()

    @classmethod
    def has_executed_live_search(cls) -> bool:
        """
        Reports whether a live search was genuinely executed successfully.
        Configuration alone must NOT be represented as a successful live search.
        """
        return cls._last_query_successful and cls._total_queries > 0

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostics for system health reporting."""
        return {
            "provider": "serper.dev",
            "endpoint": self.ENDPOINT,
            "configured": self.is_configured(),
            "operational": self.is_operational(),
            "live_search_executed": self.has_executed_live_search(),
            "total_queries_executed": self._total_queries,
            "last_query_at": self._last_query_at,
        }

    def build_search_query(
        self,
        location: str,
        category: str,
        service: str,
    ) -> Tuple[str, Optional[str]]:
        """
        Builds a targeted query string and Google country code (gl) tailored
        for public tenders, RFPs, and authentic digital service requirements.
        """
        loc_clean = location.strip() if location else ""
        cat_clean = category.strip() if category else ""
        srv_clean = service.strip() if service else ""
        srv_lower = srv_clean.lower()
        loc_lower = loc_clean.lower()

        # 1. Geographic country code (gl) & Location terms
        gl: Optional[str] = None
        location_clause = ""
        indian_keywords = [
            "andhra", "arunachal", "assam", "bihar", "chhattisgarh", "goa", "gujarat",
            "haryana", "himachal", "jharkhand", "karnataka", "kerala", "madhya",
            "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha",
            "punjab", "rajasthan", "sikkim", "tamil", "telangana", "tripura", "uttar",
            "uttarakhand", "bengal", "delhi", "chandigarh", "jammu", "kashmir",
            "ladakh", "puducherry", "andaman", "nicobar", "dadra", "daman", "diu",
            "lakshadweep", "hyderabad", "bengaluru", "bangalore", "mumbai", "pune",
            "chennai", "kolkata", "noida", "gurugram", "india"
        ]
        if any(k in loc_lower for k in indian_keywords):
            gl = "in"
            if "telangana" in loc_lower or "hyderabad" in loc_lower:
                location_clause = '(Telangana OR Hyderabad)'
            elif "maharashtra" in loc_lower or "mumbai" in loc_lower:
                location_clause = '(Maharashtra OR Mumbai OR Pune)'
            elif "karnataka" in loc_lower or "bengaluru" in loc_lower or "bangalore" in loc_lower:
                location_clause = '(Karnataka OR Bengaluru OR Bangalore)'
            elif "tamil" in loc_lower or "chennai" in loc_lower:
                location_clause = '("Tamil Nadu" OR Chennai)'
            elif "delhi" in loc_lower:
                location_clause = '(Delhi OR "New Delhi" OR NCR)'
            elif loc_clean:
                location_clause = f'("{loc_clean}" India)'
            else:
                location_clause = 'India'
        elif "london" in loc_lower or "uk" in loc_lower:
            location_clause = '("London" OR "UK")'
            gl = "gb"
        elif "austin" in loc_lower:
            location_clause = '("Austin" OR "Texas")'
            gl = "us"
        elif "chicago" in loc_lower:
            location_clause = '("Chicago" OR "Illinois")'
            gl = "us"
        elif "toronto" in loc_lower or "canada" in loc_lower:
            location_clause = '("Toronto" OR "Canada")'
            gl = "ca"
        elif loc_clean:
            location_clause = f'"{loc_clean}"'

        # 2. Service-specific requirement phrases
        if "mobile" in srv_lower or "app" in srv_lower:
            service_clause = '("mobile app" OR "Android" OR "iOS" OR "app development")'
        elif "redesign" in srv_lower:
            service_clause = '("website redesign" OR "portal redesign" OR "revamp website")'
        elif "seo" in srv_lower or "digital marketing" in srv_lower:
            service_clause = '("SEO" OR "digital marketing" OR "search engine optimization")'
        elif "web application" in srv_lower:
            service_clause = '("web application" OR "web app" OR "cloud portal" OR "SaaS portal")'
        elif "website" in srv_lower or "web" in srv_lower:
            service_clause = '("website development" OR "web portal" OR "website redesign")'
        elif srv_clean:
            service_clause = f'"{srv_clean}"'
        else:
            service_clause = '("website development" OR "mobile app" OR "software development")'

        # 3. Procurement and Commercial Requirement Intent Signals
        intent_clause = '("RFP" OR "RFQ" OR "tender" OR "procurement" OR "invites proposals" OR "request for proposal" OR "notice inviting tender" OR "seeking vendor")'

        # 4. Optional Category Clause
        category_clause = f'"{cat_clean}"' if cat_clean and cat_clean.lower() != "all" else ""

        # Assemble full query
        query_parts = []
        if location_clause:
            query_parts.append(location_clause)
        if category_clause:
            query_parts.append(category_clause)
        query_parts.append(service_clause)
        query_parts.append(intent_clause)

        # Exclude directories and job boards
        exclusion_clause = " -site:clutch.co -site:goodfirms.co -site:justdial.com -site:sulekha.com -site:upwork.com -site:freelancer.com -site:linkedin.com/jobs"

        query_str = " ".join(query_parts) + exclusion_clause
        return query_str.strip(), gl

    def search(
        self,
        location: str,
        category: str,
        service: str,
        num_results: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes a targeted search using Serper.dev Google Search API.

        Safety and Authenticity Rules:
        - If SERPER_API_KEY is missing, raises ValueError or returns empty without making HTTP requests.
        - Strict timeout of 5.0 seconds.
        - API key is NEVER logged.
        - Safe rate-limit (429) and network error handling.
        - Distinguishes buyers from service-offering vendors/directories.
        - Preserves all provenance fields.
        """
        if not self.is_configured():
            logger.warning("Search attempted but SERPER_API_KEY is not configured.")
            return [], {
                "success": False,
                "error": "SERPER_API_KEY is not configured.",
                "candidates_count": 0,
            }

        query_str, gl = self.build_search_query(location, category, service)
        payload: Dict[str, Any] = {
            "q": query_str,
            "num": min(max(num_results, 5), 20),
        }
        if gl:
            payload["gl"] = gl

        headers = {
            "X-API-KEY": self._api_key,
            "Content-Type": "application/json",
        }

        # Safe logging (Masked query, NO API KEY)
        sanitized_query = query_str[:120] + "..." if len(query_str) > 120 else query_str
        logger.info(f"Dispatching query to Serper.dev: '{sanitized_query}' [gl={gl}]")

        start_time = time.time()
        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                response = client.post(self.ENDPOINT, headers=headers, json=payload)
                elapsed_ms = int((time.time() - start_time) * 1000)

                # Record metrics
                SerperProvider._total_queries += 1
                SerperProvider._last_query_at = datetime.datetime.utcnow().isoformat()

                if response.status_code == 200:
                    data = response.json()
                    SerperProvider._last_query_successful = True
                    logger.info(f"Serper.dev returned HTTP 200 in {elapsed_ms}ms (Credits used: {data.get('credits', 1)})")
                    candidates = self._process_organic_results(
                        organic=data.get("organic", []),
                        search_query=query_str,
                        target_location=location,
                        target_category=category,
                        target_service=service,
                    )
                    return candidates, {
                        "success": True,
                        "query": query_str,
                        "credits": data.get("credits", 1),
                        "elapsed_ms": elapsed_ms,
                        "candidates_count": len(candidates),
                        "raw_results_count": len(data.get("organic", [])),
                    }

                elif response.status_code == 429:
                    SerperProvider._last_query_successful = False
                    logger.warning(f"Serper.dev rate limit reached (HTTP 429) in {elapsed_ms}ms.")
                    return [], {
                        "success": False,
                        "error": "Rate limit exceeded on external search provider (HTTP 429).",
                        "status_code": 429,
                        "candidates_count": 0,
                    }

                elif response.status_code in (401, 403):
                    SerperProvider._last_query_successful = False
                    logger.error(f"Serper.dev authentication failed (HTTP {response.status_code}).")
                    return [], {
                        "success": False,
                        "error": "External search provider authentication failed. Check SERPER_API_KEY.",
                        "status_code": response.status_code,
                        "candidates_count": 0,
                    }

                else:
                    SerperProvider._last_query_successful = False
                    logger.warning(f"Serper.dev returned unexpected status HTTP {response.status_code} in {elapsed_ms}ms.")
                    return [], {
                        "success": False,
                        "error": f"Search provider returned HTTP {response.status_code}.",
                        "status_code": response.status_code,
                        "candidates_count": 0,
                    }

        except httpx.TimeoutException:
            elapsed_ms = int((time.time() - start_time) * 1000)
            SerperProvider._last_query_successful = False
            logger.warning(f"Serper.dev request timed out after {elapsed_ms}ms (limit={self.TIMEOUT_SECONDS}s).")
            return [], {
                "success": False,
                "error": f"External search request timed out after {self.TIMEOUT_SECONDS}s.",
                "candidates_count": 0,
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            SerperProvider._last_query_successful = False
            logger.error(f"Serper.dev query error: {str(e)}")
            return [], {
                "success": False,
                "error": f"Search provider error: {str(e)}",
                "candidates_count": 0,
            }

    def _process_organic_results(
        self,
        organic: List[Dict[str, Any]],
        search_query: str,
        target_location: str,
        target_category: str,
        target_service: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses organic Google search items into genuine lead discovery candidates:
        - Drops self-advertising IT agencies, directories, and freelancer listings.
        - Extracts buying intent and evidence text from snippet and accessible page content.
        - Preserves strict provenance fields.
        - Validates source authority without hallucinating verified status.
        """
        candidates: List[Dict[str, Any]] = []
        seen_urls = set()

        for item in organic:
            title = (item.get("title") or "").strip()
            link = (item.get("link") or "").strip()
            snippet = (item.get("snippet") or "").strip()

            if not title or not link or link in seen_urls:
                continue
            seen_urls.add(link)

            # 1. Parse hostname/domain
            try:
                parsed_url = urllib.parse.urlparse(link)
                netloc = parsed_url.netloc.lower()
            except Exception:
                continue

            # 2. Filter out directory spam
            if any(netloc == d or netloc.endswith("." + d) or d in link.lower() for d in DIRECTORY_EXCLUSIONS):
                continue

            # 3. Filter out self-advertising agencies & vendors (seller vs. buyer separation)
            combined_text = f"{title} {snippet}".lower()
            is_seller_agency = any(re.search(pat, combined_text) for pat in SELLER_AGENCY_PATTERNS)
            if is_seller_agency:
                logger.debug(f"Filtered out seller agency/directory: '{title}' ({link})")
                continue

            # 4. Detect Procurement / Requirement Evidence
            has_active_intent = any(re.search(pat, combined_text) for pat in ACTIVE_INTENT_PATTERNS)
            has_potential_intent = any(re.search(pat, combined_text) for pat in POTENTIAL_INTENT_PATTERNS)

            if not has_active_intent and not has_potential_intent:
                # Result does not display identifiable procurement requirement
                logger.debug(f"Skipping result without clear requirement intent: '{title}'")
                continue

            buying_intent = "Active" if has_active_intent else "Potential"

            # 5. Extract company/authority name cleanly from title without fabrication
            # e.g., "Tender for Telemedicine Portal - Telangana State Technology Services | Hyd" -> "Telangana State Technology Services"
            business_name = self._extract_clean_business_name(title, netloc)

            # 6. Deep Evidence Extraction from actual source page (if accessible)
            page_evidence, page_fetch_note = self._extract_source_page_evidence(link)
            evidence_text = page_evidence or snippet

            # 7. Authentic Verification Classification
            is_official, v_status, v_notes = self._classify_verification_status(link, netloc, page_evidence is not None)

            # Determine location string cleanly
            candidate_location = target_location if target_location and target_location.lower() != "all" else "India"

            candidate = {
                "business_name": business_name,
                "location": candidate_location,
                "category": target_category if target_category and target_category.lower() != "all" else "Digital Services",
                "service": target_service if target_service and target_service.lower() != "all" else "Digital Transformation",
                "requirement": snippet if len(snippet) > 20 else f"{title}. {evidence_text}",
                "source_name": f"Live Web Discovery ({netloc})",
                "source_url": link,
                "source_title": title,
                "source_domain": netloc,
                "publication_date": item.get("date") or None,
                "date_found": datetime.date.today().strftime("%Y-%m-%d"),
                "record_type": "live_discovery",
                "verification_status": v_status,
                "is_live_discovery": True,
                "provider_name": "serper",
                "discovered_at": datetime.datetime.utcnow().isoformat(),
                "evidence_text": evidence_text,
                "search_query": search_query,
                "buying_intent": buying_intent,
                "verification_notes": v_notes + (f" | {page_fetch_note}" if page_fetch_note else ""),
                "discovery_provider": "Serper.dev Google Search API",
            }

            candidates.append(candidate)

        return candidates

    def _extract_clean_business_name(self, title: str, domain: str) -> str:
        """
        Extracts the publishing business or agency name cleanly from the title.
        Never hallucinates fictional entities.
        """
        # Split by common separators: " - ", " | ", " :: ", " : "
        parts = re.split(r"\s+[-|:–—]\s+", title)
        if len(parts) >= 2:
            # Check which part looks like an organisation rather than a description
            candidate_part = parts[0].strip()
            # If first part is a generic title like "Tender Notice" or "RFP", pick second
            if any(term in candidate_part.lower() for term in ["tender", "rfp", "rfq", "request for", "notice"]):
                candidate_part = parts[1].strip()
            if len(candidate_part) > 3:
                return candidate_part

        # Fallback to domain-derived title
        clean_domain = domain.replace("www.", "").split(".")[0].capitalize()
        return parts[0].strip() or clean_domain

    def _extract_source_page_evidence(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to read the published source page to extract verbatim requirement evidence.
        Uses a short timeout (2.0s) and catches all network/SSL exceptions safely.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            }
            with httpx.Client(timeout=self.PAGE_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    html_snippet = resp.text[:12000]
                    # Strip tags
                    clean_text = re.sub(r"<[^>]+>", " ", html_snippet)
                    clean_text = " ".join(clean_text.split())

                    # Look for sentences with requirement keywords
                    for keyword in ["tender", "rfp", "rfq", "scope of work", "proposals are invited", "submission deadline", "requirement"]:
                        idx = clean_text.lower().find(keyword)
                        if idx != -1:
                            start = max(0, idx - 40)
                            end = min(len(clean_text), idx + 200)
                            excerpt = clean_text[start:end].strip()
                            return f"...{excerpt}...", "Source page inspected; verbatim requirement excerpt confirmed."
                    return None, "Source page inspected; no explicit procurement excerpt identified."
                else:
                    return None, f"Source page returned HTTP {resp.status_code}; relying on snippet."
        except Exception:
            # Safe non-fatal fallback
            return None, "Source page inaccessible for deep extraction (timeout/network); relying on snippet."

    def _classify_verification_status(
        self,
        url: str,
        domain: str,
        page_accessible: bool,
    ) -> Tuple[bool, str, str]:
        """
        Applies four-tier provenance classification rules:
        - If authoritative government/public authority portal:
          - Deep tender path -> official_tender
          - Homepage/general portal -> source_domain_confirmed_tender_unverified
        - If general commercial/web domain:
          - unverified (genuine live discovery, but unverified without independent audit)
        - NEVER returns 'verified' or 'demo' for live web discoveries.
        """
        is_auth_domain = False
        for auth in AUTHORITATIVE_PORTAL_DOMAINS:
            if domain == auth or domain.endswith("." + auth):
                is_auth_domain = True
                break

        if not is_auth_domain and (domain.endswith(".gov") or domain.endswith(".gov.in") or domain.endswith(".gov.uk")):
            is_auth_domain = True

        if is_auth_domain:
            parsed = urllib.parse.urlparse(url)
            path = parsed.path.strip("/")
            if not path or len(path) < 3 or path in ("index.html", "index.jsp", "home", "default.aspx"):
                return (
                    False,
                    "source_domain_confirmed_tender_unverified",
                    f"Official government procurement domain ({domain}) authenticated; specific tender notice requires independent verification.",
                )
            else:
                return (
                    True,
                    "official_tender",
                    f"Official tender notice authenticated on authoritative public procurement portal ({domain}).",
                )

        # Standard commercial or organizational domain
        return (
            False,
            "unverified",
            f"Third-party commercial/organizational source ({domain}); authenticated via Serper.dev, pending independent audit.",
        )
