from dataclasses import dataclass

import httpx

from crawler import CrawlResult, crawl_site
from readiness import ReadinessResult, compute_readiness


@dataclass
class ScanResult:
    crawl: CrawlResult
    readiness: ReadinessResult


async def run_scan(url: str) -> ScanResult:
    async with httpx.AsyncClient() as client:
        crawl = await crawl_site(url, client=client)
    return ScanResult(crawl=crawl, readiness=compute_readiness(crawl))
