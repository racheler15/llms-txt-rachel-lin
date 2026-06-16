from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from changes import detect_changes
from crawler import CrawlResult, crawl_site
from db import get_domain_id, load_generation_hashes, page_hash_map, save_scan
from readiness import ReadinessResult, compute_readiness
from url_utils import display_domain


@dataclass
class ScanResult:
    crawl: CrawlResult
    readiness: ReadinessResult
    has_content_changes: bool = False
    domain_id: int | None = None


async def run_scan(url: str, *, persist: bool = True) -> ScanResult:
    async with httpx.AsyncClient() as client:
        crawl = await crawl_site(url, client=client)
    readiness = compute_readiness(crawl)

    has_content_changes = False
    domain_id = None
    if persist:
        hostname = urlparse(url).hostname or ""
        display_name = display_domain(hostname)
        current_hashes = page_hash_map(crawl.pages)
        existing_id = get_domain_id(display_name)
        generation_hashes = load_generation_hashes(existing_id) if existing_id else {}
        has_content_changes = detect_changes(generation_hashes, current_hashes)
        domain_id = save_scan(
            url=url,
            display_name=display_name,
            pages=crawl.pages,
            readiness=readiness,
        )

    return ScanResult(
        crawl=crawl,
        readiness=readiness,
        has_content_changes=has_content_changes,
        domain_id=domain_id,
    )
