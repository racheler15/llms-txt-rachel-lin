from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from urllib.parse import urlparse

from db import finalize_generation, get_stored_scan, init_db, list_recent_scans, mark_viewed
from models import (
    CrawlRequest,
    GenerateResponse,
    ReadinessCategoryResponse,
    ReadinessResponse,
    RecrawlResponse,
    ScanResponse,
    ScanSummaryResponse,
)
from readiness import ReadinessResult
from regenerate import build_llms_txt, recrawl_domain
from scan import run_scan
from scheduler import start_scheduler, stop_scheduler
from url_utils import display_domain

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    sched_task, sched_stop = start_scheduler()
    yield
    await stop_scheduler(sched_task, sched_stop)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _normalize_domain_param(domain: str) -> str:
    return display_domain(domain.strip().lower().removeprefix("www."))


def _to_readiness_response(result: ReadinessResult) -> ReadinessResponse:
    return ReadinessResponse(
        total=result.total,
        max_total=result.max_total,
        categories=[
            ReadinessCategoryResponse(
                id=category.id,
                score=category.score,
                max_score=category.max_score,
                label=category.label,
            )
            for category in result.categories
        ],
        recommendations=result.recommendations,
    )


def _to_scan_response(stored: dict) -> ScanResponse:
    return ScanResponse(
        domain=stored["domain"],
        url=stored["url"],
        llms_txt=stored["llms_txt"],
        pages_crawled=stored["pages_crawled"],
        pages_included=stored["pages_included"],
        readiness=_to_readiness_response(stored["readiness"]),
        has_content_changes=stored["has_content_changes"],
        has_unviewed_changes=stored["has_unviewed_changes"],
        last_scanned_at=stored["last_scanned_at"],
    )


def _to_recrawl_response(stored: dict, *, content_changed: bool, regenerated: bool) -> RecrawlResponse:
    return RecrawlResponse(
        domain=stored["domain"],
        url=stored["url"],
        pages_crawled=stored["pages_crawled"],
        pages_included=stored["pages_included"],
        readiness=_to_readiness_response(stored["readiness"]),
        has_content_changes=stored["has_content_changes"],
        has_unviewed_changes=stored["has_unviewed_changes"],
        last_scanned_at=stored["last_scanned_at"],
        llms_txt=stored["llms_txt"],
        content_changed=content_changed,
        regenerated=regenerated,
    )


@app.get("/scans", response_model=list[ScanSummaryResponse])
async def list_scans():
    return [ScanSummaryResponse(**scan) for scan in list_recent_scans()]


@app.get("/scans/{domain}", response_model=ScanResponse)
async def get_scan(domain: str):
    stored = get_stored_scan(_normalize_domain_param(domain))
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    return _to_scan_response(stored)


@app.post("/scans/{domain}/mark-viewed", response_model=ScanResponse)
async def mark_scan_viewed(domain: str):
    display_name = _normalize_domain_param(domain)
    stored = get_stored_scan(display_name)
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    mark_viewed(display_name)
    updated = get_stored_scan(display_name)
    if not updated:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    return _to_scan_response(updated)


@app.post("/scans/{domain}/recrawl", response_model=RecrawlResponse)
async def recrawl_scan(domain: str):
    display_name = _normalize_domain_param(domain)
    stored = get_stored_scan(display_name)
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    result = await recrawl_domain(display_name, stored["url"], mark_unviewed=False)
    updated = get_stored_scan(display_name)
    if not updated:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    return _to_recrawl_response(
        updated,
        content_changed=result.content_changed,
        regenerated=result.regenerated,
    )


@app.post("/scans/{domain}/refresh", response_model=RecrawlResponse)
async def refresh_scan(domain: str):
    return await recrawl_scan(domain)


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: CrawlRequest):
    scan = await run_scan(str(request.url))
    pages = scan.crawl.pages
    if not pages:
        raise HTTPException(status_code=404, detail="No pages could be crawled from this site.")

    llms_txt, pages_included = await build_llms_txt(pages)
    hostname = urlparse(str(request.url)).hostname or ""
    domain = display_domain(hostname)

    finalize_generation(domain, llms_txt=llms_txt, pages_included=pages_included)

    return GenerateResponse(
        llms_txt=llms_txt,
        domain=domain,
        pages_crawled=len(pages),
        pages_included=pages_included,
        readiness=_to_readiness_response(scan.readiness),
        has_content_changes=False,
        has_unviewed_changes=False,
    )
