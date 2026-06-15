import hashlib

import tldextract
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from constants import HARD_SKIP_PATTERNS
from models import Page


def registrable_domain(hostname: str) -> str:
    """Return the registrable domain (e.g. stripe.com, example.co.uk) from a hostname."""
    host = hostname.lower().removeprefix("www.")
    if not host:
        return ""

    extracted = tldextract.extract(host)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return host


def display_domain(hostname: str) -> str:
    """Return registrable domain, falling back to bare hostname."""
    normalized = hostname.lower().removeprefix("www.")
    return registrable_domain(hostname) or normalized


def is_internal_link(url: str, base_domain: str) -> bool:
    """True when url belongs to the same registrable domain (includes subdomains)."""
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    hostname = hostname.lower()
    base_domain = base_domain.lower()
    return hostname == base_domain or hostname.endswith(f".{base_domain}")


def normalize_url(url: str) -> str:
    """Lowercase host, strip trailing slash and fragment, sort and filter query params."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    params = parse_qs(parsed.query)
    filtered_params = {k: v for k, v in params.items() if not k.startswith("utm_")}
    query = urlencode(sorted(filtered_params.items()), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def page_quality(page: Page) -> tuple:
    """Ranking key for picking the best Page when URLs collapse to the same canonical."""
    description = page.description or page.h1 or page.title or ""
    has_query = bool(urlparse(page.url).query)
    return (
        page.in_sitemap,
        page.sitemap_priority or 0.0,
        len(description),
        page.inbound_count,
        -page.depth,
        0 if has_query else 1,
    )


def dedupe_pages(pages: list[Page]) -> list[Page]:
    """Keep one Page per normalized URL, preferring the highest-quality metadata."""
    best: dict[str, Page] = {}
    for page in pages:
        key = normalize_url(page.url)
        if key not in best or page_quality(page) > page_quality(best[key]):
            best[key] = page
    return list(best.values())


def url_hash(url: str) -> str:
    """Hash a URL string for dedup."""
    return hashlib.md5(url.encode()).hexdigest()


def content_hash(text: str) -> str:
    """Hash page body text for content dedup."""
    return hashlib.md5(text.strip().encode()).hexdigest()


def should_skip_url(path: str, query: str) -> bool:
    """Exclude URLs with hard-skip path patterns or noisy query params."""
    if any(pattern in path for pattern in HARD_SKIP_PATTERNS):
        return True
    if any(param in query for param in ("page=", "ref=", "utm_")):
        return True
    return False
