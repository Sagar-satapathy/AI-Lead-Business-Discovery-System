"""
backend/services/mwmbl_provider.py - Mwmbl Open-Source Public Search API Adapter (Phase 3.1: Strict Buyer Intent & Date Separation)

Official Open-Source Search Provider for ₹0 Budget Live Discovery:
1. Public Endpoint: https://api.mwmbl.org/api/v1/search/
2. Policy Compliance: Keyless, non-profit, open-source search API. Strictly uses official JSON API.
   NO website scraping.
3. Budget & Cost Guarantee: 100% Free (₹0 cost).
4. Demand-Oriented Search: Generates targeted queries with location, industry, requested service,
   and specific demand signals (requirements, tenders, RFPs, redesigns).
5. Strict Buyer vs Seller Separation:
   - Digital service providers, IT agencies, portfolios, and case studies are classified as 'Unqualified'
     (sellers showcasing previous work, NOT organisations purchasing website development).
   - Portfolios and past projects (e.g. swaragh.com/portfolio-healthcare) are explicitly disqualified.
6. 3-Tier Classification & Relevance Filtering:
   - Active: Direct evidence of an explicit requirement, tender, RFP, or formal procurement notice.
   - Potential: Relevant organisation in target industry with specific, evidence-supported possible unmet need
     (e.g. website redesign announcement, request for agency proposals, portal overhaul).
   - Unqualified: Service sellers, portfolios, platforms, directories, tutorials, or organisations
     without demand signals ("Never infer buying intent from an organisation's existence").
7. Publication-Date Validation:
   - discovered_at records the UTC timestamp when the system discovered the page.
   - publication_date contains only genuine source publication dates; defaults to None (JSON null).
   - NEVER copies today's date into publication_date.
"""

import os
import re
import time
import logging
import datetime
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger("mwmbl_provider")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [MwmblProvider] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

AUTHORITATIVE_PORTAL_DOMAINS = [
    "gov.in",
    "nic.in",
    "telangana.gov.in",
    "gov.uk",
    "sam.gov",
    "austintexas.gov",
    "chicago.gov",
    "toronto.ca",
]

# Domains excluded as platforms, templates, code repos, directories, forums, and general media
DISQUALIFICATION_DOMAINS = [
    "github.com",
    "wix.com",
    "notion.so",
    "themeisle.com",
    "loopple.com",
    "shopify.com",
    "wordpress.org",
    "wordpress.com",
    "medium.com",
    "stackoverflow.com",
    "stackexchange.com",
    "reddit.com",
    "habr.com",
    "level1techs.com",
    "wikipedia.org",
    "wiktionary.org",
    "wikimedia.org",
    "engadget.com",
    "theguardian.com",
    "timesofindia.indiatimes.com",
    "w3.org",
    "cirkuit.net",
    "clutch.co",
    "goodfirms.co",
    "justdial.com",
    "sulekha.com",
    "upwork.com",
    "freelancer.com",
    "fiverr.com",
    "bark.com",
    "linkedin.com/jobs",
    "iclass-cms.com",
    "themekings.net",
    "frogtummy.com",
]

# Portfolio & Case Study URL patterns (sellers showcasing past work)
PORTFOLIO_URL_PATTERNS = [
    r"/portfolio",
    r"/case-stud(y|ies)",
    r"/our-work",
    r"/work(/|$)",
    r"/projects(/|$)",
    r"/clients(/|$)",
    r"/showcase",
]

# Portfolio & Case Study content patterns
PORTFOLIO_CONTENT_PATTERNS = [
    r"\bportfolios?\b",
    r"\bcase\s+stud(y|ies)\b",
    r"\bour\s+work\b",
    r"\bfeatured\s+work\b",
    r"\bclient\s+showcase\b",
    r"\bprevious\s+projects?\b",
    r"\bsuccess\s+stor(y|ies)\b",
    r"\bwhat\s+we('ve|\s+have)?\s+done\b",
    r"\bcheck\s+out\s+(the|our)\s+portfolio\b",
]

# Agency / seller indicators (firms offering services, NOT buying)
AGENCY_SELLER_PATTERNS = [
    r"\bour\s+services\b",
    r"\bwe\s+build\b",
    r"\bwe\s+design\b",
    r"\bwe\s+develop\b",
    r"\bweb\s+design\s+company\b",
    r"\bweb\s+development\s+company\b",
    r"\bwebsite\s+development\s+company\b",
    r"\b(website|web|software|app|digital|it)\s+(design|development|solutions)\s+(company|agency|firm|services|consultancy|provider)\b",
    r"\b(healthcare|education|retail|ecommerce)\s+website\s+(design|development|solutions)\s+(company|agency|firm)\b",
    r"\bwork\s+with\s+(an?\s+)?.*(website|development)\s+company\b",
    r"\bweb\s+development\s+agency\b",
    r"\bdigital\s+marketing\s+agency\b",
    r"\bhire\s+(dedicated\s+)?developers\b",
    r"\bcustom\s+website\s+development\b",
    r"\bleading\s+(global\s+)?digital\s+marketing\b",
    r"\bhand-build\s+fast\b",
    r"\bdigital\s+transformation\s+company\b",
    r"\bwebsite\s+development\s+services\b",
    r"\bclients\s+we\s+have\s+worked\s+with\b",
    r"\btechnologies\b.*(\bportfolio\b|\bservices\b)",
    r"\bsoftware\s+solutions\s+company\b",
]

# Explicit procurement, RFP, tender, and contract signals
ACTIVE_DEMAND_PATTERNS = [
    r"\btender\b",
    r"\brfp\b",
    r"\brfq\b",
    r"\bprocurement(\s+notice)?\b",
    r"\bbid\s+submission\b",
    r"\bnotice\s+inviting\b",
    r"\bproposals\s+are\s+invited\b",
    r"\bbids\s+are\s+invited\b",
    r"\bclosing\s+date\b",
    r"\be-tender\b",
    r"\bexpression\s+of\s+interest\b",
    r"\brequest\s+for\s+proposals?\b",
    r"\brequest\s+for\s+quotes?\b",
]

# Strict unmet requirement signals (portfolios and generic descriptions strictly excluded)
POTENTIAL_DEMAND_PATTERNS = [
    r"\bseeking\s+(an?\s+)?(agency|vendor|partner|developer|team|firm)\s+(for|to\s+build|to\s+develop|to\s+redesign)\b",
    r"\blooking\s+to\s+(hire|engage|contract|partner\s+with)\s+(an?\s+)?(agency|vendor|developer|firm)\b",
    r"\blooking\s+for\s+(an?\s+)?(agency|vendor|developer|firm)\s+to\b",
    r"\b(announces?|plans?|scheduled)\s+(a\s+)?(website|web\s+portal)\s+redesign\b",
    r"\b(requesting|inviting)\s+proposals\s+for\s+(a\s+)?(website|portal|redesign)\b",
    r"\bseeking\s+proposals\s+for\s+(website|web\s+portal|online\s+system)\b",
    r"\bwebsite\s+redesign\s+(project|initiative|rfp|requirement)\b",
    r"\bplanning\s+to\s+(launch|overhaul|redesign|rebuild)\s+(our|its|their|the)\s+(website|portal|online\s+store)\b",
    r"\b(hospital|clinic|school|university|retailer|merchant|district)\s+(seeking|soliciting|requiring)\s+(website|portal|app)\b",
    r"\bdigital\s+transformation\s+(requirement|initiative|rfp)\s+for\s+(new\s+)?(website|portal)\b",
    r"\bpatient\s+portal\s+(development|implementation|redesign)\s+requirement\b",
    r"\bstudent\s+portal\s+(development|implementation|redesign)\s+requirement\b",
    r"\be-commerce\s+(portal|store|website)\s+(development|launch)\s+requirement\b",
    # Broader, evidence-based commercial demand signals (not limited to published tenders).
    r"\b(needs?|seeks?|looking\s+to\s+improve|aims?\s+to\s+improve|plans?\s+to\s+improve)\b.{0,90}\b(digital\s+presence|online\s+presence|online\s+visibility|social\s+media|patient\s+outreach|digital\s+marketing|search\s+visibility)\b",
    r"\b(digital\s+marketing|social\s+media|google\s+ads|seo|search\s+engine\s+optimisation|search\s+engine\s+optimization|online\s+advertising)\b.{0,70}\b(requirement|campaign|initiative|expansion|growth|improve|increase|launch|budget)\b",
    r"\b(patient\s+acquisition|appointment\s+bookings|online\s+leads|website\s+traffic|brand\s+awareness)\b.{0,70}\b(growth|campaign|marketing|improve|increase|strategy)\b",
]

# Industry-specific entity & domain terms
CATEGORY_ENTITY_TERMS = {
    "healthcare": [
        r"\bhospital\b", r"\bclinic\b", r"\bhealthcare\b", r"\bmedical\b",
        r"\bdiagnostic\b", r"\bpatient\b", r"\bdoctor\b", r"\bhealth\b",
        r"\btelemedicine\b", r"\bpharmacy\b", r"\bpharma\b", r"\bmedicare\b",
    ],
    "education": [
        r"\bschool\b", r"\bcollege\b", r"\buniversity\b", r"\binstitute\b",
        r"\bacademy\b", r"\beducation\b", r"\bcampus\b", r"\bstudent\b",
        r"\bacademic\b", r"\bfaculty\b", r"\bedtech\b",
    ],
    "retail": [
        r"\bretail\b", r"\bstore\b", r"\bshop\b", r"\becommerce\b",
        r"\be-commerce\b", r"\bmerchant\b", r"\bcart\b", r"\bboutique\b",
        r"\bmerchandise\b", r"\bproducts\b", r"\bsupermarket\b",
    ],
    "retail & e-commerce": [
        r"\bretail\b", r"\bstore\b", r"\bshop\b", r"\becommerce\b",
        r"\be-commerce\b", r"\bmerchant\b", r"\bcart\b", r"\bboutique\b",
        r"\bmerchandise\b", r"\bproducts\b", r"\bsupermarket\b",
    ],
    "logistics & supply chain": [
        r"\blogistics\b", r"\btransport\b", r"\bfreight\b", r"\bwarehouse\b",
        r"\bfleet\b", r"\bshipping\b", r"\bcargo\b", r"\bsupply\s+chain\b",
    ],
    "financial services": [
        r"\bbank\b", r"\bfintech\b", r"\binsurance\b", r"\bfinance\b",
        r"\bwealth\b", r"\binvestment\b", r"\bcredit\b",
    ],
    "legal": [
        r"\blaw\s+firm\b", r"\blegal\b", r"\battorney\b", r"\blawyer\b",
        r"\bcourt\b", r"\bcompliance\b", r"\blaw\b",
    ],
}

GENERIC_TITLE_NOISE = {
    "website development",
    "web development",
    "website design",
    "best website development company",
    "ecommerce website development",
    "home",
    "portfolio",
    "about us",
    "contact us",
    "overview",
    "official website",
    "services",
    "company",
}


def clean_organisation_name(title: str, domain: str) -> str:
    """
    Extracts the actual organisation / brand name without adopting
    generic webpage titles (e.g. 'Website Development') verbatim.
    """
    parts = re.split(r"\s+[-|:–—•/]\s+", title or "")

    for p in parts:
        p_clean = p.strip()
        if len(p_clean) > 2 and p_clean.lower() not in GENERIC_TITLE_NOISE:
            if not any(
                g in p_clean.lower()
                for g in [
                    "website development",
                    "web development",
                    "web design",
                    "digital marketing",
                    "top 10",
                    "best company",
                ]
            ):
                return p_clean

    dom_clean = domain.lower().replace("www.", "")
    dom_root = dom_clean.split(".")[0]
    org_from_dom = re.sub(r"[-_]", " ", dom_root).strip().title()
    return org_from_dom or domain


def extract_publication_date(item: dict, text: str) -> Optional[str]:
    """
    Extracts genuine publication date from search metadata or source text.
    Returns ISO date (YYYY-MM-DD) if established; otherwise None (JSON null).
    NEVER defaults to today's date.
    """
    # 1. Direct item metadata if provided by source engine
    raw_date = item.get("date") or item.get("published_date") or item.get("publication_date") or item.get("published")
    if raw_date and isinstance(raw_date, str):
        m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", raw_date)
        if m:
            return m.group(1)

    # 2. Extract explicit date pattern in text (e.g. 'Published: 2026-09-14' or 'Date: 2026-08-01')
    m_text = re.search(r"\b(?:published|posted|date|dated)[:\s]+(20\d{2}-\d{2}-\d{2})\b", text, re.IGNORECASE)
    if m_text:
        return m_text.group(1)

    return None


class MwmblProvider:
    """
    Adapter for Mwmbl open-source search engine public API.
    Activated when DISCOVERY_PROVIDER == 'mwmbl'.
    Features Phase 3.1 Quality Hardening:
    - Strict buyer vs seller / portfolio separation.
    - Strict unmet requirement signals for Potential classification.
    - Publication-date validation (never defaulted to today; separate from discovered_at).
    - Clear attribution of technology providers vs buyer organisations.
    """

    ENDPOINT = "https://api.mwmbl.org/api/v1/search/"
    TIMEOUT_SECONDS = 12.0

    _total_queries: int = 0
    _last_query_at: Optional[str] = None
    _last_query_successful: bool = False

    def is_configured(self) -> bool:
        """Mwmbl is an open-source public API and requires no API key."""
        return True

    def is_operational(self) -> bool:
        """Returns True if Mwmbl is available for queries."""
        return True

    @classmethod
    def has_executed_live_search(cls) -> bool:
        return cls._last_query_successful and cls._total_queries > 0

    @classmethod
    def reset_state_for_testing(cls) -> None:
        cls._total_queries = 0
        cls._last_query_at = None
        cls._last_query_successful = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "mwmbl",
            "name": "Mwmbl Open-Source Public Search",
            "endpoint": self.ENDPOINT,
            "configured": True,
            "operational": self.is_operational(),
            "free_tier": True,
            "requires_key": False,
            "live_search_executed": self.has_executed_live_search(),
            "total_queries_executed": self._total_queries,
            "last_query_at": self._last_query_at,
        }

    def build_search_queries(self, location: str, category: str, service: str) -> List[str]:
        """
        Constructs prioritized targeted buyer demand queries dynamically using location,
        industry/category, and requested digital service.
        Avoids hardcoded service assumptions and generic agency-attracting phrases.
        Incorporates buyer-intent keywords (RFP, tender, empanelment, hiring, requirement).
        """
        loc_clean = (location or "").strip()
        cat_clean = (category or "").strip()
        srv_clean = (service or "").strip()

        loc_token = loc_clean.split(",")[0].strip() if loc_clean else "Hyderabad"
        if loc_token.lower() == "all":
            loc_token = ""

        # Normalize service phrase
        srv_core = srv_clean
        if not srv_core or srv_core.lower() == "all":
            srv_core = "digital services"

        cat_lower = cat_clean.lower()
        entity_noun = ""
        if "healthcare" in cat_lower:
            entity_noun = "hospital"
        elif "education" in cat_lower:
            entity_noun = "school"
        elif "retail" in cat_lower:
            entity_noun = "retail store"
        elif "legal" in cat_lower:
            entity_noun = "law firm"
        elif "financial" in cat_lower:
            entity_noun = "bank"

        queries = []

        # 1. Primary Buyer RFP & Proposal Query
        if cat_clean and cat_clean.lower() != "all":
            queries.append(f"{loc_token} {cat_clean} {srv_core} RFP".strip())
        else:
            queries.append(f"{loc_token} {srv_core} RFP".strip())

        # 2. Public / Commercial Tender & Procurement Query
        if cat_clean and cat_clean.lower() != "all":
            queries.append(f"{loc_token} {cat_clean} {srv_core} tender".strip())
        else:
            queries.append(f"{loc_token} {srv_core} tender".strip())

        # 3. Agency Empanelment / Vendor Solicitation Query
        if cat_clean and cat_clean.lower() != "all":
            queries.append(f"{loc_token} {cat_clean} {srv_core} agency empanelment".strip())
        else:
            queries.append(f"{loc_token} {srv_core} vendor empanelment".strip())

        # 4. Explicit Requirement Query (satisfies requirement demand signals)
        if cat_clean and cat_clean.lower() != "all":
            queries.append(f"{loc_token} {cat_clean} {srv_core} agency requirement".strip())
        else:
            queries.append(f"{loc_token} {srv_core} requirement".strip())

        # 5. Entity-specific hiring / engagement query
        if entity_noun:
            queries.append(f"{loc_token} {entity_noun} hiring {srv_core} agency".strip())

        # 6-7. Broader commercial opportunity discovery. These searches surface
        # organisations discussing a business need even when no formal RFP exists.
        if "digital marketing" in srv_core.lower() or "seo" in srv_core.lower():
            queries.append(f"{loc_token} {cat_clean} improve online presence social media marketing patient outreach".strip())
            queries.append(f"{loc_token} {cat_clean} digital marketing campaign requirement agency".strip())
        elif "website" in srv_core.lower() or "web" in srv_core.lower():
            queries.append(f"{loc_token} {cat_clean} website redesign online booking portal requirement".strip())
            queries.append(f"{loc_token} {cat_clean} improve website online presence development".strip())

        unique_queries = []
        for q in queries:
            clean_q = " ".join(q.split())
            if clean_q and clean_q not in unique_queries:
                unique_queries.append(clean_q)

        return unique_queries or [f"{loc_token} {cat_clean} {srv_core} RFP".strip()]

    def build_search_query(self, location: str, category: str, service: str) -> str:
        """Returns the primary targeted query."""
        queries = self.build_search_queries(location, category, service)
        return queries[0] if queries else f"{location} {category} {service}".strip()

    def _execute_mwmbl_http(self, query_str: str) -> Tuple[int, List[Any], str]:
        """
        Dispatches HTTP GET to Mwmbl official JSON API with retry resilience.
        Returns (status_code, raw_results_list, error_msg).
        """
        params = {"s": query_str}
        headers = {"Accept": "application/json", "User-Agent": "AILeadBusinessDiscovery/2.0"}

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=self.TIMEOUT_SECONDS) as client:
                    resp = client.get(self.ENDPOINT, params=params, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
                        return 200, results, ""
                    else:
                        return resp.status_code, [], f"HTTP {resp.status_code}: {resp.text[:100]}"
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < max_attempts - 1:
                    time.sleep(0.5)
                    continue
                return 408, [], f"Mwmbl request timed out: {str(e)}"
            except Exception as e:
                return 500, [], f"Mwmbl error: {str(e)}"

        return 500, [], "Mwmbl request failed after retries."

    def search(
        self,
        location: str,
        category: str,
        service: str,
        num_results: int = 10,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Queries Mwmbl official JSON API with targeted demand queries.
        Performs 3-tier classification into Active, Potential, and Unqualified.
        Returns parsed relevant candidates and complete quality diagnostic metrics.
        """
        queries_to_run = self.build_search_queries(location, category, service)
        primary_query = queries_to_run[0]

        all_raw_items: List[Any] = []
        queries_executed: List[str] = []
        seen_urls = set()
        last_error = ""

        start_time = time.time()
        MwmblProvider._total_queries += 1
        MwmblProvider._last_query_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Execute queries (primary first; complementary if raw results < num_results)
        for q in queries_to_run:
            logger.info(f"Dispatching query to Mwmbl Public API: '{q}'")
            queries_executed.append(q)
            status_code, raw_list, err = self._execute_mwmbl_http(q)

            if status_code == 200:
                MwmblProvider._last_query_successful = True
                for item in raw_list:
                    link = (item.get("url") or item.get("link") or "").strip()
                    if link and link not in seen_urls:
                        seen_urls.add(link)
                        all_raw_items.append(item)
            else:
                last_error = err
                logger.warning(f"Query '{q}' returned status {status_code}: {err}")

            if len(all_raw_items) >= num_results * 2:
                break

        elapsed_ms = int((time.time() - start_time) * 1000)

        # Process & Classify all raw items
        relevant_candidates, unqualified_items = self._process_and_classify_results(
            results=all_raw_items,
            primary_query=primary_query,
            target_location=location,
            target_category=category,
            target_service=service,
            limit=num_results,
        )

        success = len(all_raw_items) > 0 or not last_error

        stats = {
            "success": success,
            "query": primary_query,
            "queries_executed": queries_executed,
            "provider": "mwmbl",
            "elapsed_ms": elapsed_ms,
            "raw_results_count": len(all_raw_items),
            "relevant_count": len(relevant_candidates),
            "unqualified_count": len(unqualified_items),
            "unqualified_sample": unqualified_items[:5],
            "candidates_count": len(relevant_candidates),
            "error": last_error if not success else None,
        }

        return relevant_candidates, stats

    @staticmethod
    def _flatten_value(val: Any) -> str:
        """Flattens Mwmbl bold-chunk lists into a clean single string."""
        if isinstance(val, str):
            return val.strip()
        elif isinstance(val, list):
            chunks = []
            for c in val:
                if isinstance(c, dict) and "value" in c:
                    chunks.append(str(c["value"]))
                elif isinstance(c, str):
                    chunks.append(c)
            return "".join(chunks).strip()
        return ""

    def _process_and_classify_results(
        self,
        results: List[Any],
        primary_query: str,
        target_location: str,
        target_category: str,
        target_service: str,
        limit: int = 10,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Classifies every result into:
        - Active: Direct evidence of explicit requirement, tender, RFP, or request.
        - Potential: Relevant organisation in target industry with specific evidence of possible unmet need.
        - Unqualified: Portfolios, digital-service agencies, platforms, directories, tutorials,
          or organisations without demand evidence.
        """
        relevant_candidates: List[Dict[str, Any]] = []
        unqualified_items: List[Dict[str, Any]] = []

        seen_links = set()

        for item in results:
            if not isinstance(item, dict):
                continue

            title = self._flatten_value(item.get("title"))
            link = (item.get("url") or item.get("link") or "").strip()
            extract = self._flatten_value(item.get("extract") or item.get("snippet") or item.get("description"))

            if not title or not link or link in seen_links:
                continue
            seen_links.add(link)

            try:
                parsed = urllib.parse.urlparse(link)
                domain = parsed.netloc.lower()
                url_path = parsed.path.lower()
            except Exception:
                domain = ""
                url_path = ""

            combined_text = f"{title} {extract}".lower()

            # Clean organisation name extraction
            business_name = clean_organisation_name(title, domain)

            # Extract genuine source publication date (NEVER default to today)
            pub_date = extract_publication_date(item, extract)

            # -------------------------------------------------------------
            # STEP 1: Exclusion of Platforms, Repos, Templates, Forums, News
            # -------------------------------------------------------------
            is_platform_or_tool = any(d in domain for d in DISQUALIFICATION_DOMAINS)
            if is_platform_or_tool:
                unqualified_items.append({
                    "url": link,
                    "title": title,
                    "domain": domain,
                    "organisation": business_name,
                    "classification": "Unqualified",
                    "reason": f"Software platform, code repository, template, forum, or aggregator ({domain})",
                    "evidence_snippet": extract[:160],
                })
                continue

            # -------------------------------------------------------------
            # STEP 2: Strict Exclusion of Portfolios & Case Studies (Sellers)
            # -------------------------------------------------------------
            is_portfolio_url = any(re.search(pat, url_path) for pat in PORTFOLIO_URL_PATTERNS)
            is_portfolio_content = any(re.search(pat, combined_text) for pat in PORTFOLIO_CONTENT_PATTERNS)
            if is_portfolio_url or is_portfolio_content:
                unqualified_items.append({
                    "url": link,
                    "title": title,
                    "domain": domain,
                    "organisation": business_name,
                    "classification": "Unqualified",
                    "reason": "Digital-service provider/portfolio; no evidence of the organisation purchasing website development.",
                    "evidence_snippet": extract[:160],
                })
                continue

            # -------------------------------------------------------------
            # STEP 3: Strict Exclusion of IT Agencies / Digital Service Sellers
            # -------------------------------------------------------------
            is_agency_seller = any(re.search(pat, combined_text) for pat in AGENCY_SELLER_PATTERNS)
            if is_agency_seller:
                unqualified_items.append({
                    "url": link,
                    "title": title,
                    "domain": domain,
                    "organisation": business_name,
                    "classification": "Unqualified",
                    "reason": "Digital-service provider / IT agency offering services (seller, not buyer).",
                    "evidence_snippet": extract[:160],
                })
                continue

            # -------------------------------------------------------------
            # STEP 4: Industry / Category Relevance Filter
            # -------------------------------------------------------------
            target_cat_clean = (target_category or "").lower().strip()
            industry_patterns = CATEGORY_ENTITY_TERMS.get(target_cat_clean, [])
            if not industry_patterns:
                industry_patterns = [rf"\b{re.escape(target_cat_clean)}\b"] if target_cat_clean and target_cat_clean != "all" else []

            matches_industry = True
            if industry_patterns:
                matches_industry = any(re.search(pat, combined_text) for pat in industry_patterns)

            if not matches_industry:
                unqualified_items.append({
                    "url": link,
                    "title": title,
                    "domain": domain,
                    "organisation": business_name,
                    "classification": "Unqualified",
                    "reason": f"Irrelevant industry; page does not relate to target category '{target_category}'",
                    "evidence_snippet": extract[:160],
                })
                continue

            # -------------------------------------------------------------
            # STEP 5: Demand Evaluation (Active vs Potential vs Unqualified)
            # -------------------------------------------------------------
            has_active_intent = any(re.search(pat, combined_text) for pat in ACTIVE_DEMAND_PATTERNS)
            has_potential_intent = any(re.search(pat, combined_text) for pat in POTENTIAL_DEMAND_PATTERNS)

            # Government domain check
            is_gov_portal = any(domain == a or domain.endswith("." + a) for a in AUTHORITATIVE_PORTAL_DOMAINS)

            if has_active_intent:
                classification = "Active"
                if is_gov_portal:
                    has_tender_ref = bool(re.search(r"\b(nit|ref|tender\s+no|bid\s+no|closing\s+date|deadline)\b", combined_text))
                    v_status = "official_tender" if has_tender_ref else "source_domain_confirmed_tender_unverified"
                    v_notes = f"Official portal discovery ({domain}); contains active tender/procurement demand signals."
                else:
                    v_status = "unverified"
                    v_notes = f"Commercial procurement notice discovered via Mwmbl ({domain}); unverified pending direct RFP audit."

                identified_req = extract if len(extract) > 20 else title

                candidate = {
                    "business_name": business_name,
                    "location": target_location or "Hyderabad, Telangana, India",
                    "category": target_category or "Healthcare",
                    "service": target_service or "Website Development",
                    "requirement": identified_req,
                    "source_name": f"Mwmbl Open-Source Search ({domain})",
                    "source_url": link,
                    "source_title": title,
                    "source_domain": domain,
                    "publication_date": pub_date,  # None if unknown; never defaults to today
                    "date_found": datetime.date.today().strftime("%Y-%m-%d"),
                    "record_type": "live_discovery",
                    "verification_status": v_status,
                    "is_live_discovery": True,
                    "provider_name": "mwmbl",
                    "discovered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "evidence_text": extract or title,
                    "search_query": primary_query,
                    "buying_intent": "Active",
                    "classification_reason": "Direct evidence of explicit requirement, tender, RFP or procurement notice",
                    "verification_notes": v_notes,
                    "discovery_provider": "Mwmbl Open-Source Public Search",
                }
                relevant_candidates.append(candidate)

            elif has_potential_intent:
                classification = "Potential"
                v_status = "unverified"
                v_notes = f"Relevant organisation in {target_category} with evidence-supported possible unmet requirement. Unverified commercial discovery."
                identified_req = extract if len(extract) > 20 else title

                candidate = {
                    "business_name": business_name,
                    "location": target_location or "Hyderabad, Telangana, India",
                    "category": target_category or "Healthcare",
                    "service": target_service or "Website Development",
                    "requirement": identified_req,
                    "source_name": f"Mwmbl Open-Source Search ({domain})",
                    "source_url": link,
                    "source_title": title,
                    "source_domain": domain,
                    "publication_date": pub_date,  # None if unknown; never defaults to today
                    "date_found": datetime.date.today().strftime("%Y-%m-%d"),
                    "record_type": "live_discovery",
                    "verification_status": v_status,
                    "is_live_discovery": True,
                    "provider_name": "mwmbl",
                    "discovered_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "evidence_text": extract or title,
                    "search_query": primary_query,
                    "buying_intent": "Potential",
                    "classification_reason": "Relevant organisation with specific, evidence-supported possible unmet requirement",
                    "verification_notes": v_notes,
                    "discovery_provider": "Mwmbl Open-Source Public Search",
                }
                relevant_candidates.append(candidate)

            else:
                # Organisation exists but provides zero evidence of an unmet buying requirement
                unqualified_items.append({
                    "url": link,
                    "title": title,
                    "domain": domain,
                    "organisation": business_name,
                    "classification": "Unqualified",
                    "reason": "Organisation exists but provides zero evidence of an unmet buying requirement or demand (existence alone does not indicate intent).",
                    "evidence_snippet": extract[:160],
                })

            if len(relevant_candidates) >= limit:
                break

        return relevant_candidates, unqualified_items
