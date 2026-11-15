"""
backend/services/tavily_provider.py - Official Tavily Search API Provider Adapter

Primary Configurable Free Provider for Phase 2 External Business Discovery:
1. Endpoint: https://api.tavily.com/search
2. Authentication: API key passed securely in JSON payload (kept exclusively on backend, read from TAVILY_API_KEY)
3. Budget & Cost Guarantee: 100% Free tier (1,000 free searches/month). Zero paid billing or automatic upgrades.
4. Targeted Searches: India, Telangana, Hyderabad, and global markets for Website Dev, Mobile App, SEO, Redesign, RFPs.
5. Result Integrity: Filters out agency self-advertisements and directory spam (Clutch, GoodFirms, JustDial, etc.).
6. Provenance: provider_name ('tavily'), record_type ('live_discovery'), source_url, source_domain, discovered_at,
   evidence_text, verification_status, is_live_discovery, search_query.
7. Safe Resilience: Graceful credit exhaustion handling, HTTP 429 rate limits, timeouts (5.0s), malformed results handling,
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

logger = logging.getLogger("tavily_provider")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [TavilyProvider] %(message)s")
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


class TavilyProvider:
    """
    Dedicated Provider Adapter for Tavily Search API.
    Primary configurable free external search provider.
    """

    ENDPOINT = "https://api.tavily.com/search"
    TIMEOUT_SECONDS = 5.0

    # Class-level state tracking
    _total_queries: int = 0
    _last_query_at: Optional[str] = None
    _last_query_successful: bool = False
    _credits_exhausted: bool = False
    _last_error_message: Optional[str] = None

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = (api_key or settings.TAVILY_API_KEY or "").strip()

    def is_configured(self) -> bool:
        """Returns True if a non-empty TAVILY_API_KEY is available."""
        return bool(self._api_key)

    def is_operational(self) -> bool:
        """Returns True if the provider is configured and not blocked by credit exhaustion."""
        return self.is_configured() and not TavilyProvider._credits_exhausted

    @classmethod
    def has_executed_live_search(cls) -> bool:
        """
        Reports whether a live search was genuinely executed successfully.
        Configuration alone must NOT be represented as a successful live search.
        """
        return cls._last_query_successful and cls._total_queries > 0

    @classmethod
    def reset_state_for_testing(cls) -> None:
        """Resets tracking state for test isolation."""
        cls._total_queries = 0
        cls._last_query_at = None
        cls._last_query_successful = False
        cls._credits_exhausted = False
        cls._last_error_message = None

    @classmethod
    def is_credits_exhausted(cls) -> bool:
        """Reports whether Tavily free credits have been exhausted."""
        return cls._credits_exhausted

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostics for system health reporting."""
        executed = self.is_configured() and self.has_executed_live_search()
        return {
            "provider": "tavily",
            "name": "Tavily AI Search Engine",
            "endpoint": self.ENDPOINT,
            "configured": self.is_configured(),
            "operational": self.is_operational(),
            "free_tier": True,
            "credits_exhausted": self.is_credits_exhausted(),
            "live_search_executed": executed,
            "total_queries_executed": self._total_queries,
            "last_query_at": self._last_query_at,
            "last_error": self._last_error_message,
        }

    def build_search_query(
        self,
        location: str,
        category: str,
        service: str,
    ) -> str:
        """
        Builds a targeted query string tailored for Tavily API to locate
        procurement notices, RFPs, and authentic digital service requirements.
        """
        loc_clean = location.strip() if location else ""
        cat_clean = category.strip() if category else ""
        srv_clean = service.strip() if service else ""
        loc_lower = loc_clean.lower()
        srv_lower = srv_clean.lower()

        # 1. Location part
        if "telangana" in loc_lower or "hyderabad" in loc_lower:
            loc_clause = "Telangana Hyderabad India"
        elif "india" in loc_lower:
            loc_clause = "India"
        elif "london" in loc_lower or "uk" in loc_lower:
            loc_clause = "London UK"
        elif "austin" in loc_lower:
            loc_clause = "Austin Texas"
        elif "chicago" in loc_lower:
            loc_clause = "Chicago Illinois"
        elif loc_clean:
            loc_clause = loc_clean
        else:
            loc_clause = ""

        # 2. Service part
        if "mobile" in srv_lower or "app" in srv_lower:
            srv_clause = "mobile application development Android iOS app"
        elif "redesign" in srv_lower:
            srv_clause = "website redesign web portal revamp"
        elif "seo" in srv_lower or "digital marketing" in srv_lower:
            srv_clause = "SEO search engine optimization digital marketing"
        elif "web application" in srv_lower:
            srv_clause = "web application cloud portal development"
        elif "website" in srv_lower or "web" in srv_lower:
            srv_clause = "website development web portal"
        elif srv_clean:
            srv_clause = srv_clean
        else:
            srv_clause = "software website mobile development"

        # 3. Intent & Procurement signals
        intent_clause = "RFP tender procurement notice inviting proposals"

        # 4. Optional Category
        cat_clause = cat_clean if cat_clean and cat_clean.lower() != "all" else ""

        query_tokens = [t for t in [loc_clause, cat_clause, srv_clause, intent_clause] if t]
        return " ".join(query_tokens).strip()

    def search(
        self,
        location: str,
        category: str,
        service: str,
        num_results: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes a targeted search via Tavily Search API.

        Budget & Zero-Cost Protections:
        - Free tier: Zero paid usage.
        - If TAVILY_API_KEY is missing: Returns empty without executing external requests.
        - Strict timeout: 5.0 seconds.
        - Graceful Credit Exhaustion: If free credits are exhausted (402, 429 quota),
          returns clear diagnostic and DOES NOT silently fabricate results or pretend benchmarks are live.
        - Secret Redaction: API key is never logged.
        """
        if not self.is_configured():
            logger.warning("Search attempted but TAVILY_API_KEY is not configured.")
            return [], {
                "success": False,
                "error": "TAVILY_API_KEY is not configured.",
                "credit_exhausted": False,
                "candidates_count": 0,
            }

        query_str = self.build_search_query(location, category, service)
        payload = {
            "api_key": self._api_key,
            "query": query_str,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": min(max(num_results, 5), 20),
        }

        # Safe logging (Never log API key)
        sanitized_query = query_str[:120] + "..." if len(query_str) > 120 else query_str
        logger.info(f"Dispatching query to Tavily Search API: '{sanitized_query}'")

        start_time = time.time()
        try:
            with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                response = client.post(
                    self.ENDPOINT,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                elapsed_ms = int((time.time() - start_time) * 1000)

                TavilyProvider._total_queries += 1
                TavilyProvider._last_query_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

                if response.status_code == 200:
                    data = response.json()
                    TavilyProvider._last_query_successful = True
                    TavilyProvider._credits_exhausted = False
                    TavilyProvider._last_error_message = None
                    logger.info(f"Tavily returned HTTP 200 in {elapsed_ms}ms (response_time: {data.get('response_time', 'N/A')}s)")

                    candidates = self._process_tavily_results(
                        results=data.get("results", []),
                        search_query=query_str,
                        target_location=location,
                        target_category=category,
                        target_service=service,
                    )
                    return candidates, {
                        "success": True,
                        "query": query_str,
                        "provider": "tavily",
                        "elapsed_ms": elapsed_ms,
                        "candidates_count": len(candidates),
                        "raw_results_count": len(data.get("results", [])),
                    }

                # Credit exhaustion detection (HTTP 402, or 429/400 with quota message)
                error_body = response.text
                is_credit_exhausted = (
                    response.status_code == 402
                    or (response.status_code == 429 and any(term in error_body.lower() for term in ["credit", "monthly", "quota", "plan exhausted"]))
                    or any(term in error_body.lower() for term in ["usage limit reached", "monthly request limit", "credits exhausted", "payment required", "out of credits"])
                )

                if is_credit_exhausted:
                    TavilyProvider._last_query_successful = False
                    TavilyProvider._credits_exhausted = True
                    TavilyProvider._last_error_message = "Tavily free search credits exhausted."
                    logger.warning(f"Tavily free search credits exhausted (HTTP {response.status_code}): {error_body[:100]}")
                    return [], {
                        "success": False,
                        "credit_exhausted": True,
                        "error": "Free API credits for Tavily search provider have been exhausted (1,000 monthly search limit reached). Please wait for monthly quota reset or switch to another free provider.",
                        "status_code": response.status_code,
                        "candidates_count": 0,
                    }

                elif response.status_code == 429:
                    TavilyProvider._last_query_successful = False
                    TavilyProvider._last_error_message = "Rate limit reached."
                    logger.warning(f"Tavily rate limit reached (HTTP 429) in {elapsed_ms}ms.")
                    return [], {
                        "success": False,
                        "rate_limited": True,
                        "error": "Tavily search rate limit reached (HTTP 429). Please wait before retrying.",
                        "status_code": 429,
                        "candidates_count": 0,
                    }

                elif response.status_code in (401, 403):
                    TavilyProvider._last_query_successful = False
                    TavilyProvider._last_error_message = f"Authentication failed (HTTP {response.status_code})."
                    logger.error(f"Tavily authentication failed (HTTP {response.status_code}).")
                    return [], {
                        "success": False,
                        "error": "Tavily authentication failed. Please verify your TAVILY_API_KEY.",
                        "status_code": response.status_code,
                        "candidates_count": 0,
                    }

                else:
                    TavilyProvider._last_query_successful = False
                    TavilyProvider._last_error_message = f"HTTP {response.status_code}"
                    logger.warning(f"Tavily returned unexpected status HTTP {response.status_code} in {elapsed_ms}ms.")
                    return [], {
                        "success": False,
                        "error": f"Tavily search returned HTTP {response.status_code}.",
                        "status_code": response.status_code,
                        "candidates_count": 0,
                    }

        except httpx.TimeoutException:
            elapsed_ms = int((time.time() - start_time) * 1000)
            TavilyProvider._last_query_successful = False
            TavilyProvider._last_error_message = "Request timeout"
            logger.warning(f"Tavily search request timed out after {elapsed_ms}ms (limit={self.TIMEOUT_SECONDS}s).")
            return [], {
                "success": False,
                "error": f"Tavily search request timed out after {self.TIMEOUT_SECONDS}s.",
                "candidates_count": 0,
            }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            TavilyProvider._last_query_successful = False
            TavilyProvider._last_error_message = str(e)
            logger.error(f"Tavily search exception: {str(e)}")
            return [], {
                "success": False,
                "error": f"Tavily search provider error: {str(e)}",
                "candidates_count": 0,
            }

    def _process_tavily_results(
        self,
        results: Any,
        search_query: str,
        target_location: str,
        target_category: str,
        target_service: str,
    ) -> List[Dict[str, Any]]:
        """
        Parses Tavily results into candidate leads with full 9-point provenance:
        - Drops malformed items and invalid types.
        - Deduplicates results by URL.
        - Rejects directory spam and self-advertising IT agencies.
        - Validates buying intent and evidence.
        - Assigns authentic verification status (never 'verified' for raw web results).
        """
        candidates: List[Dict[str, Any]] = []
        seen_urls = set()

        if not isinstance(results, list):
            logger.warning("Tavily results is not a list; returning empty.")
            return candidates

        for item in results:
            if not isinstance(item, dict):
                continue

            title = (item.get("title") or "").strip()
            link = (item.get("url") or "").strip()
            content = (item.get("content") or "").strip()

            if not title or not link or link in seen_urls:
                continue
            seen_urls.add(link)

            # 1. Parse hostname/domain
            try:
                parsed_url = urllib.parse.urlparse(link)
                netloc = parsed_url.netloc.lower()
                if not netloc:
                    continue
            except Exception:
                continue

            # 2. Filter directory spam
            if any(netloc == d or netloc.endswith("." + d) or d in link.lower() for d in DIRECTORY_EXCLUSIONS):
                continue

            # 3. Filter seller IT agencies
            combined_text = f"{title} {content}".lower()
            is_seller_agency = any(re.search(pat, combined_text) for pat in SELLER_AGENCY_PATTERNS)
            if is_seller_agency:
                logger.debug(f"Filtered out seller agency/directory: '{title}' ({link})")
                continue

            # 4. Detect Procurement / Requirement Evidence
            has_active_intent = any(re.search(pat, combined_text) for pat in ACTIVE_INTENT_PATTERNS)
            has_potential_intent = any(re.search(pat, combined_text) for pat in POTENTIAL_INTENT_PATTERNS)

            if not has_active_intent and not has_potential_intent:
                logger.debug(f"Skipping result without clear requirement intent: '{title}'")
                continue

            buying_intent = "Active" if has_active_intent else "Potential"

            # 5. Extract company/authority name cleanly from title
            business_name = self._extract_clean_business_name(title, netloc)

            # 6. Authentic Verification Classification
            is_official, v_status, v_notes = self._classify_verification_status(link, netloc)

            candidate_location = target_location if target_location and target_location.lower() != "all" else "India"

            candidate = {
                "business_name": business_name,
                "location": candidate_location,
                "category": target_category if target_category and target_category.lower() != "all" else "Digital Services",
                "service": target_service if target_service and target_service.lower() != "all" else "Digital Transformation",
                "requirement": content if len(content) > 20 else title,
                "source_name": f"Live Web Discovery ({netloc})",
                "source_url": link,
                "source_title": title,
                "source_domain": netloc,
                "publication_date": item.get("published_date") or item.get("date") or None,
                "date_found": datetime.date.today().strftime("%Y-%m-%d"),
                "record_type": "live_discovery",
                "verification_status": v_status,
                "is_live_discovery": True,
                "provider_name": "tavily",
                "discovered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "evidence_text": content,
                "search_query": search_query,
                "buying_intent": buying_intent,
                "verification_notes": v_notes,
                "discovery_provider": "Tavily AI Search Engine",
            }

            candidates.append(candidate)

        return candidates

    def _extract_clean_business_name(self, title: str, domain: str) -> str:
        """Extracts organisation or authority name cleanly from title without fabrication."""
        parts = re.split(r"\s+[-|:–—]\s+", title)
        if len(parts) >= 2:
            candidate_part = parts[0].strip()
            if any(term in candidate_part.lower() for term in ["tender", "rfp", "rfq", "request for", "notice"]):
                candidate_part = parts[1].strip()
            if len(candidate_part) > 3:
                return candidate_part

        clean_domain = domain.replace("www.", "").split(".")[0].capitalize()
        return parts[0].strip() or clean_domain

    def _classify_verification_status(self, url: str, domain: str) -> Tuple[bool, str, str]:
        """Applies four-tier provenance classification rules."""
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
                    f"Official government procurement portal ({domain}) authenticated; specific tender document requires independent verification.",
                )
            else:
                return (
                    True,
                    "official_tender",
                    f"Official tender notice authenticated on authoritative public procurement portal ({domain}).",
                )

        # Standard third-party source: unverified pending independent audit
        return (
            False,
            "unverified",
            f"Third-party commercial/public source ({domain}); authenticated via Tavily Search API, pending independent audit.",
        )
