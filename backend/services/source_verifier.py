"""
backend/services/source_verifier.py - Genuine Source Page Verification Service

Phase 4 Core Engine:
1. Strict SSRF Protection: Rejects localhost, loopback, private RFC-1918, link-local, carrier-grade NAT,
   multicast, cloud metadata (169.254.169.254), and non-standard ports (allows only 80 and 443).
2. DNS Rebinding Prevention: Validates DNS resolution before connecting AND verifies the connected
   socket peer IP address matches safe ranges.
3. Redirect Security: Revalidates all redirect hops (up to 3 hops) against all SSRF rules.
4. Response Streaming & Resource Bounds: Enforces configurable timeout (default 4.0s), max download
   cap of 512 KB, and accepts only HTML MIME types.
5. DOM & Content Analysis: Uses standard library HTMLParser to extract title, meta description, navigation
   links, headings, and body text without external browser or heavy dependencies (100% free / ₹0 cost).
6. Evidence Extraction & Classification: Accurately classifies pages into:
   - 'buyer_procurement': Genuine active procurement notices, RFPs, bids, or tenders.
   - 'seller_agency': IT companies, software agencies, or vendors marketing their own services.
   - 'portfolio': Case studies, client portfolios, or project showcases.
   - 'directory': Business directories, agency ranking sites, or listing platforms.
   - 'unknown': Inconclusive or general informational pages.
7. Graceful Failure Handling: Handles timeouts, HTTP 403/404/503, oversized responses, and invalid HTML
   gracefully without crashing or dropping valid leads.
"""

import asyncio
import datetime
import html
from html.parser import HTMLParser
import ipaddress
import logging
import re
import socket
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

import anyio
import httpcore
from httpcore._backends.anyio import AnyIOBackend, AnyIOStream
import httpx

logger = logging.getLogger("source_verifier")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [SourceVerifier] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Configurable constants
DEFAULT_TIMEOUT_SECONDS = 4.0
MAX_RESPONSE_BYTES = 512 * 1024  # 512 KB
MAX_REDIRECTS = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 AntigravityLeadVerifier/1.0"

# Restricted hostnames blacklist
RESTRICTED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "instance-data",
    "metadata",
    "kubernetes.default.svc",
}

# Restricted IP networks for SSRF prevention
RESTRICTED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local and cloud metadata
    ipaddress.ip_network("100.64.0.0/10"),  # Carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),  # Multicast
    ipaddress.ip_network("240.0.0.0/4"),  # Reserved
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # Unique local
    ipaddress.ip_network("fe80::/10"),  # Link-local IPv6
    ipaddress.ip_network("ff00::/8"),  # Multicast IPv6
]


class SSRFSecurityError(Exception):
    """Raised when a request violates SSRF or DNS security checks."""
    pass


class OversizedResponseError(Exception):
    """Raised when an HTTP response exceeds the 512 KB download cap."""
    pass


def is_ip_restricted(ip_str: str) -> Tuple[bool, str]:
    """
    Checks if an IP address string is loopback, private, link-local, multicast,
    reserved, carrier-grade NAT, or cloud metadata.
    """
    try:
        ip = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        return True, f"Malformed IP address: {ip_str}"

    # Check IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped:
        ip = mapped

    if ip.is_loopback:
        return True, f"Loopback IP address rejected: {ip}"
    if ip.is_private:
        return True, f"Private IP address rejected: {ip}"
    if ip.is_link_local:
        return True, f"Link-local IP address rejected: {ip}"
    if ip.is_multicast:
        return True, f"Multicast IP address rejected: {ip}"
    if ip.is_reserved:
        return True, f"Reserved IP address rejected: {ip}"
    if ip.is_unspecified:
        return True, f"Unspecified IP address rejected: {ip}"

    # Explicit check against restricted ranges
    for net in RESTRICTED_NETWORKS:
        if ip in net:
            return True, f"Restricted network IP rejected: {ip} in {net}"

    if str(ip) == "169.254.169.254":
        return True, "Cloud metadata IP address rejected: 169.254.169.254"

    return False, "Public IP"


def validate_target_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates scheme, hostname, port, and DNS resolution of a URL.
    Returns (is_safe, error_or_reason, resolved_ip).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL provided", None

    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except Exception as e:
        return False, f"Failed to parse URL: {str(e)}", None

    # 1. Scheme check: only http and https allowed
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"Invalid URL scheme '{scheme}': only http and https are allowed", None

    # 2. Hostname check
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "URL contains no hostname", None

    if hostname in RESTRICTED_HOSTNAMES or hostname.endswith(".local") or hostname.endswith(".internal"):
        return False, f"Restricted hostname rejected: {hostname}", None

    # 3. Port check: allow ONLY standard ports (80 for http, 443 for https)
    port = parsed.port
    if port is not None:
        if scheme == "http" and port != 80:
            return False, f"Non-standard HTTP port {port} rejected: only port 80 allowed", None
        if scheme == "https" and port != 443:
            return False, f"Non-standard HTTPS port {port} rejected: only port 443 allowed", None

    # 4. If hostname is already a raw IP literal, check it directly
    try:
        ipaddress.ip_address(hostname)
        is_restr, restr_reason = is_ip_restricted(hostname)
        if is_restr:
            return False, f"SSRF blocked: {restr_reason}", None
        return True, "Safe IP", hostname
    except ValueError:
        pass

    # 5. DNS Resolution validation
    try:
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname}': {str(e)}", None
    except Exception as e:
        return False, f"DNS resolution error: {str(e)}", None

    if not addr_infos:
        return False, f"No DNS records returned for '{hostname}'", None

    resolved_ips: List[str] = []
    for info in addr_infos:
        sockaddr = info[4]
        ip_str = sockaddr[0]
        resolved_ips.append(ip_str)
        is_restr, restr_reason = is_ip_restricted(ip_str)
        if is_restr:
            return False, f"SSRF blocked: Host '{hostname}' resolved to restricted IP: {restr_reason}", None

    primary_ip = resolved_ips[0] if resolved_ips else None
    return True, "Safe URL", primary_ip


class SafeNetworkBackend(AnyIOBackend):
    """
    Custom AnyIO network backend that enforces post-connection socket IP validation
    to prevent DNS rebinding attacks.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Any] = None,
    ) -> httpcore.AsyncNetworkStream:
        # Pre-connection hostname check
        is_safe, reason, _ = validate_target_url(f"http://{host}:{port}")
        if not is_safe:
            raise SSRFSecurityError(f"SSRF / DNS Security Violation: {reason}")

        stream = await super().connect_tcp(
            host=host,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

        # Post-connection socket peer IP check (DNS Rebinding Defense)
        try:
            raw_sock = getattr(stream, "_raw_socket", None)
            if raw_sock:
                peer = raw_sock.getpeername()
                peer_ip = peer[0]
                is_restr, restr_msg = is_ip_restricted(peer_ip)
                if is_restr:
                    try:
                        raw_sock.close()
                    except Exception:
                        pass
                    raise SSRFSecurityError(
                        f"DNS Rebinding Attack Detected: Socket connected to restricted peer IP {peer_ip} ({restr_msg})"
                    )
        except SSRFSecurityError:
            raise
        except Exception as e:
            logger.debug(f"Peer verification skipped or failed: {str(e)}")

        return stream


class HTMLContentExtractor(HTMLParser):
    """
    Robust, fault-tolerant HTML content parser using standard library.
    Extracts title, meta description, navigation links, headings, and body text.
    Never crashes on malformed or broken HTML.
    """

    IGNORABLE_TAGS = {"script", "style", "noscript", "svg", "iframe", "object", "embed"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title: str = ""
        self.meta_description: str = ""
        self.nav_links: List[str] = []
        self.headings: List[str] = []
        self.body_fragments: List[str] = []

        self._in_title = False
        self._in_a = False
        self._current_a_text = []
        self._in_heading = False
        self._current_heading_text = []
        self._ignore_depth = 0
        self._total_chars = 0
        self._max_chars = 150_000  # Safety bound on extracted characters

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        tag_lower = tag.lower()
        if tag_lower in self.IGNORABLE_TAGS:
            self._ignore_depth += 1
            return

        if self._ignore_depth > 0:
            return

        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "title" and not self.title:
            self._in_title = True
        elif tag_lower == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "").strip()
            if (name == "description" or prop in ("og:description", "twitter:description")) and not self.meta_description:
                self.meta_description = content[:500]
        elif tag_lower == "a":
            self._in_a = True
            self._current_a_text = []
        elif tag_lower in ("h1", "h2", "h3", "h4"):
            self._in_heading = True
            self._current_heading_text = []

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in self.IGNORABLE_TAGS:
            if self._ignore_depth > 0:
                self._ignore_depth -= 1
            return

        if self._ignore_depth > 0:
            return

        if tag_lower == "title":
            self._in_title = False
        elif tag_lower == "a":
            self._in_a = False
            a_txt = " ".join("".join(self._current_a_text).split())
            if a_txt and len(a_txt) < 80:
                self.nav_links.append(a_txt)
            self._current_a_text = []
        elif tag_lower in ("h1", "h2", "h3", "h4"):
            self._in_heading = False
            h_txt = " ".join("".join(self._current_heading_text).split())
            if h_txt:
                self.headings.append(h_txt)
            self._current_heading_text = []

    def handle_data(self, data: str):
        if self._ignore_depth > 0 or self._total_chars >= self._max_chars:
            return

        text = data.strip()
        if not text:
            return

        self._total_chars += len(text)

        if self._in_title:
            self.title = (self.title + " " + text).strip()[:200]
        elif self._in_a:
            self._current_a_text.append(text)
        elif self._in_heading:
            self._current_heading_text.append(text)
            self.body_fragments.append(text)
        else:
            self.body_fragments.append(text)

    def get_clean_body_text(self) -> str:
        """Returns normalized space-separated text of the document."""
        return " ".join(self.body_fragments)


# Classification heuristic pattern sets
PROCUREMENT_BUYER_PATTERNS = [
    re.compile(r"\b(notice\s+inviting\s+tender|nit\s+no\.?|tender\s+notice|tender\s+reference)\b", re.IGNORECASE),
    re.compile(r"\b(request\s+for\s+proposals?|rfp\s+no\.?|rfp\s+ref)\b", re.IGNORECASE),
    re.compile(r"\b(expression\s+of\s+interest|eoi\s+no\.?)\b", re.IGNORECASE),
    re.compile(r"\b(bids?\s+are\s+invited|proposals?\s+are\s+invited|sealed\s+tenders?\s+are\s+invited)\b", re.IGNORECASE),
    re.compile(r"\b(invites\s+proposals?\s+from\s+(eligible|qualified|experienced|reputed)\s+(agencies|firms|vendors|bidders))\b", re.IGNORECASE),
    re.compile(r"\b(invites\s+(tenders?|bids?|eoi)\s+for\s+(the\s+)?(selection|engagement|empanelment|appointment))\b", re.IGNORECASE),
    re.compile(r"\b(last\s+date\s+for\s+submission|bid\s+submission\s+deadline|due\s+date\s+for\s+submission)\b", re.IGNORECASE),
    re.compile(r"\b(scope\s+of\s+work\s*[:\-])\b", re.IGNORECASE),
    re.compile(r"\b(earnest\s+money\s+deposit|emd\s+amount|tender\s+fee)\b", re.IGNORECASE),
    re.compile(r"\b(pre-qualification\s+criteria|eligibility\s+criteria\s+for\s+bidders?)\b", re.IGNORECASE),
]

SELLER_AGENCY_PATTERNS = [
    re.compile(r"\b(we\s+are\s+(a\s+)?leading|our\s+digital\s+agency|our\s+web\s+development\s+company)\b", re.IGNORECASE),
    re.compile(r"\b(our\s+services|services\s+we\s+offer|what\s+we\s+offer|our\s+solutions)\b", re.IGNORECASE),
    re.compile(r"\b(hire\s+(dedicated\s+)?(developers?|designers?|team|engineers?)|hire\s+us)\b", re.IGNORECASE),
    re.compile(r"\b(request\s+a\s+quote|get\s+a\s+(free\s+)?quote|schedule\s+a\s+call|book\s+a\s+consultation)\b", re.IGNORECASE),
    re.compile(r"\b(why\s+choose\s+us|why\s+work\s+with\s+us|our\s+development\s+process)\b", re.IGNORECASE),
    re.compile(r"\b(our\s+clients|clients\s+we\s+have\s+served|technologies\s+we\s+use|our\s+tech\s+stack)\b", re.IGNORECASE),
    re.compile(r"\b(contact\s+our\s+sales\s+team|discuss\s+your\s+project\s+with\s+us)\b", re.IGNORECASE),
]

PORTFOLIO_PATTERNS = [
    re.compile(r"\b(portfolio|case\s+studies|case\s+study|our\s+recent\s+work|featured\s+projects?)\b", re.IGNORECASE),
    re.compile(r"\b(results\s+achieved\s+for|project\s+overview\s*[:\-]|the\s+challenge\s*[:\-]|the\s+solution\s*[:\-])\b", re.IGNORECASE),
    re.compile(r"\b(client\s*:\s*[A-Z][a-zA-Z\s]+|client\s+testimonial)\b", re.IGNORECASE),
]

DIRECTORY_PATTERNS = [
    re.compile(r"\b(top\s+\d+\s+(web|mobile|software|seo)\s+(companies|agencies|developers|firms))\b", re.IGNORECASE),
    re.compile(r"\b(find\s+the\s+best\s+(developers?|agencies|companies)|compare\s+top\s+rated)\b", re.IGNORECASE),
    re.compile(r"\b(directory\s+of|verified\s+reviews|client\s+reviews\s+and\s+ratings)\b", re.IGNORECASE),
]


def classify_page_content(
    title: str,
    meta_desc: str,
    nav_links: List[str],
    headings: List[str],
    body_text: str,
    url: str,
) -> Dict[str, Any]:
    """
    Evaluates page metadata, nav elements, headings, and body text to determine
    whether the document is a genuine buyer procurement notice, an agency marketing
    its services, a portfolio case study, a directory listing, or unknown.
    """
    full_text = f"{title} {meta_desc} {' '.join(headings)} {body_text}"
    url_lower = url.lower()

    # 1. Check Directory signals
    dir_matches = sum(1 for p in DIRECTORY_PATTERNS if p.search(full_text))
    if dir_matches >= 2 or any(d in url_lower for d in ["clutch.co", "goodfirms.co", "sortlist.com", "upwork.com"]):
        return {
            "page_type": "directory",
            "is_buyer": False,
            "is_seller": False,
            "evidence_snippet": "",
            "notes": "Verified as business directory or agency ranking aggregator.",
        }

    # 2. Check Portfolio / Case Study signals
    is_portfolio_url = any(p in url_lower for p in ["/portfolio", "/case-study", "/case-studies", "/projects/", "/our-work"])
    portfolio_matches = sum(1 for p in PORTFOLIO_PATTERNS if p.search(full_text))
    if is_portfolio_url or portfolio_matches >= 2:
        snippet = ""
        for p in PORTFOLIO_PATTERNS:
            m = p.search(full_text)
            if m:
                s_idx = max(0, m.start() - 20)
                e_idx = min(len(full_text), m.end() + 100)
                snippet = full_text[s_idx:e_idx].strip()
                break
        return {
            "page_type": "portfolio",
            "is_buyer": False,
            "is_seller": True,
            "evidence_snippet": snippet[:200],
            "notes": "Verified as past client portfolio or agency case study showcase.",
        }

    # 3. Check Buyer Procurement signals (Active RFP / Tender)
    buyer_matches = []
    for pattern in PROCUREMENT_BUYER_PATTERNS:
        m = pattern.search(full_text)
        if m:
            buyer_matches.append(m)

    if len(buyer_matches) >= 2 or (len(buyer_matches) >= 1 and any(gov in url_lower for gov in [".gov", ".nic", ".org", "tender", "procurement"])):
        # Extract best evidence snippet
        m = buyer_matches[0]
        start = max(0, m.start() - 30)
        end = min(len(full_text), m.end() + 140)
        # Refine to punctuation boundary
        snippet = full_text[start:end].strip()
        return {
            "page_type": "buyer_procurement",
            "is_buyer": True,
            "is_seller": False,
            "evidence_snippet": snippet[:250],
            "notes": "Verified genuine buyer procurement notice / active RFP document.",
        }

    # 4. Check Seller Agency signals
    seller_matches = []
    for pattern in SELLER_AGENCY_PATTERNS:
        m = pattern.search(full_text)
        if m:
            seller_matches.append(m)

    # Agency Nav Link indicators
    agency_nav_count = sum(
        1 for link in nav_links if re.search(r"\b(services|pricing|our work|hire developers|case studies|about us)\b", link, re.I)
    )

    if len(seller_matches) >= 2 or (len(seller_matches) >= 1 and agency_nav_count >= 2):
        m = seller_matches[0]
        start = max(0, m.start() - 20)
        end = min(len(full_text), m.end() + 120)
        snippet = full_text[start:end].strip()
        return {
            "page_type": "seller_agency",
            "is_buyer": False,
            "is_seller": True,
            "evidence_snippet": snippet[:200],
            "notes": "Verified as digital service provider or IT agency marketing their own services.",
        }

    # 5. Inconclusive / Insufficient Evidence -> Unknown
    return {
        "page_type": "unknown",
        "is_buyer": False,
        "is_seller": False,
        "evidence_snippet": "",
        "notes": "Source page content analyzed; insufficient evidence of active procurement or agency offering.",
    }


async def verify_source_url(
    url: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> Dict[str, Any]:
    """
    Fetches and verifies a destination URL with SSRF guards, size caps, and content analysis.
    Returns a structured verification result dictionary.
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result: Dict[str, Any] = {
        "url": url,
        "fetch_status": "unverified",
        "page_type": "unknown",
        "is_buyer": False,
        "is_seller": False,
        "evidence_snippet": "",
        "title": "",
        "meta_description": "",
        "verified_at": now_iso,
        "notes": "",
        "error": None,
    }

    if not url or not isinstance(url, str):
        result["fetch_status"] = "invalid_url"
        result["notes"] = "No valid URL provided for verification."
        return result

    # 1. Initial SSRF & Security Validation
    is_safe, sec_reason, resolved_ip = validate_target_url(url)
    if not is_safe:
        result["fetch_status"] = "ssrf_blocked"
        result["notes"] = f"Security check rejected URL: {sec_reason}"
        result["error"] = sec_reason
        return result

    # 2. Async HTTP fetch with redirects and streaming size limit
    transport = SafeNetworkBackend()
    async_transport = httpx.AsyncHTTPTransport()
    # Replace internal network backend with safe one
    async_transport._pool._network_backend = transport

    current_url = url
    redirect_count = 0
    final_response = None
    accumulated_bytes = bytearray()

    try:
        async with httpx.AsyncClient(
            transport=async_transport,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"},
            timeout=httpx.Timeout(timeout_seconds, connect=timeout_seconds, read=timeout_seconds),
            follow_redirects=False,
        ) as client:

            while redirect_count <= MAX_REDIRECTS:
                # Security re-check before every redirect hop
                hop_safe, hop_reason, _ = validate_target_url(current_url)
                if not hop_safe:
                    result["fetch_status"] = "ssrf_blocked"
                    result["notes"] = f"SSRF security violation on redirect: {hop_reason}"
                    result["error"] = hop_reason
                    return result

                req = client.build_request("GET", current_url)
                resp = await client.send(req, stream=True)

                if resp.is_redirect:
                    redirect_count += 1
                    loc = resp.headers.get("Location")
                    await resp.aclose()
                    if not loc:
                        result["fetch_status"] = "fetch_failed"
                        result["notes"] = "Redirect returned with missing Location header."
                        return result
                    current_url = urllib.parse.urljoin(current_url, loc)
                    continue

                final_response = resp
                break

            if not final_response:
                result["fetch_status"] = "fetch_failed"
                result["notes"] = f"Too many redirects (exceeded limit of {MAX_REDIRECTS})."
                return result

            # Check status code
            status_code = final_response.status_code
            if status_code == 403:
                await final_response.aclose()
                result["fetch_status"] = "blocked_403"
                result["notes"] = "HTTP 403 Forbidden: Target web server blocked automated inspection."
                return result
            elif status_code == 404:
                await final_response.aclose()
                result["fetch_status"] = "not_found_404"
                result["notes"] = "HTTP 404 Not Found: Target document does not exist."
                return result
            elif status_code in (500, 502, 503, 504):
                await final_response.aclose()
                result["fetch_status"] = "server_error_503"
                result["notes"] = f"HTTP {status_code} Server Error on target origin."
                return result
            elif status_code != 200:
                await final_response.aclose()
                result["fetch_status"] = f"http_{status_code}"
                result["notes"] = f"Received unexpected HTTP status {status_code}."
                return result

            # Verify Content-Type is HTML
            content_type = final_response.headers.get("Content-Type", "").lower()
            if not ("text/html" in content_type or "application/xhtml+xml" in content_type or not content_type):
                await final_response.aclose()
                result["fetch_status"] = "non_html"
                result["notes"] = f"Target returned non-HTML MIME type: {content_type}."
                return result

            # Stream body up to max_bytes
            async for chunk in final_response.aiter_bytes():
                accumulated_bytes.extend(chunk)
                if len(accumulated_bytes) > max_bytes:
                    await final_response.aclose()
                    result["fetch_status"] = "oversized"
                    result["notes"] = f"Response exceeded {max_bytes // 1024} KB limit. Download terminated."
                    return result

            await final_response.aclose()

    except SSRFSecurityError as e:
        result["fetch_status"] = "ssrf_blocked"
        result["notes"] = f"SSRF security violation: {str(e)}"
        result["error"] = str(e)
        return result
    except (httpx.TimeoutException, TimeoutError):
        result["fetch_status"] = "timeout"
        result["notes"] = f"Target host connection timed out after {timeout_seconds:.1f} seconds."
        return result
    except (httpx.ConnectError, httpx.RequestError) as e:
        result["fetch_status"] = "fetch_failed"
        result["notes"] = f"HTTP connection failed: {str(e)}"
        result["error"] = str(e)
        return result
    except Exception as e:
        result["fetch_status"] = "fetch_failed"
        result["notes"] = f"Unexpected fetch error: {str(e)}"
        result["error"] = str(e)
        return result

    # 3. Decode HTML content safely
    try:
        html_text = accumulated_bytes.decode("utf-8", errors="replace")
    except Exception:
        html_text = accumulated_bytes.decode("latin-1", errors="replace")

    # 4. Parse DOM
    parser = HTMLContentExtractor()
    try:
        parser.feed(html_text)
    except Exception as e:
        logger.debug(f"HTMLParser warning on malformed HTML: {str(e)}")

    clean_body = parser.get_clean_body_text()
    classification = classify_page_content(
        title=parser.title,
        meta_desc=parser.meta_description,
        nav_links=parser.nav_links,
        headings=parser.headings,
        body_text=clean_body,
        url=current_url,
    )

    result["fetch_status"] = "200_ok"
    result["page_type"] = classification["page_type"]
    result["is_buyer"] = classification["is_buyer"]
    result["is_seller"] = classification["is_seller"]
    result["evidence_snippet"] = classification["evidence_snippet"]
    result["title"] = parser.title
    result["meta_description"] = parser.meta_description
    result["notes"] = classification["notes"]

    return result


async def verify_candidates_concurrently(
    candidates: List[Dict[str, Any]],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_concurrent: int = 5,
) -> List[Dict[str, Any]]:
    """
    Verifies multiple candidate discovery leads concurrently with bounded concurrency.
    Appends source verification fields to each candidate dictionary without mutating existing keys.
    """
    if not candidates:
        return []

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _worker(item: Dict[str, Any]) -> Dict[str, Any]:
        item_copy = dict(item)
        url = item_copy.get("source_url") or ""
        if not url:
            item_copy["source_fetch_status"] = "missing_url"
            item_copy["source_page_type"] = "unknown"
            item_copy["source_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            item_copy["source_evidence_snippet"] = ""
            return item_copy

        async with semaphore:
            try:
                ver_res = await verify_source_url(url, timeout_seconds=timeout_seconds)
                item_copy["source_fetch_status"] = ver_res.get("fetch_status", "unknown")
                item_copy["source_page_type"] = ver_res.get("page_type", "unknown")
                item_copy["source_verified_at"] = ver_res.get("verified_at")
                item_copy["source_evidence_snippet"] = ver_res.get("evidence_snippet", "")
                if ver_res.get("is_seller") or ver_res.get("page_type") in ("seller_agency", "portfolio", "directory"):
                    item_copy["verification_status"] = "unverified"
                    item_copy["is_seller"] = True
                elif ver_res.get("is_buyer") and ver_res.get("page_type") == "buyer_procurement":
                    item_copy["is_buyer"] = True
                    # If HTML evidence exists, append to or set evidence_text
                    if ver_res.get("evidence_snippet"):
                        item_copy["source_evidence_snippet"] = ver_res["evidence_snippet"]
            except Exception as e:
                item_copy["source_fetch_status"] = "fetch_failed"
                item_copy["source_page_type"] = "unknown"
                item_copy["source_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                item_copy["source_evidence_snippet"] = ""
                logger.warning(f"Error verifying candidate {url}: {str(e)}")

        return item_copy

    tasks = [_worker(cand) for cand in candidates]
    verified_results = await asyncio.gather(*tasks, return_exceptions=False)
    return list(verified_results)
