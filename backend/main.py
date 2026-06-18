from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import asyncio
import json
import logging
from urllib.parse import urlparse

from crawl_errors import ScanError, error_detail, HTTP_STATUS
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


def _raise_scan_error(exc: ScanError) -> None:
    raise HTTPException(
        status_code=HTTP_STATUS[exc.error_type],
        detail=error_detail(exc),
    )


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
        js_rendering_likely=result.js_rendering_likely,
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


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _sse_streaming_response(coro_factory):
    async def event_generator():
        queue: asyncio.Queue[tuple[str, dict] | None] = asyncio.Queue()

        def on_progress(event: str, data: dict) -> None:
            queue.put_nowait((event, data))

        async def run_pipeline() -> None:
            try:
                result = await coro_factory(on_progress)
                await queue.put(("complete", result.model_dump()))
            except ScanError as exc:
                await queue.put(("error", error_detail(exc)))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run_pipeline())

        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield _sse_event(event, data)

        await task

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _run_recrawl_pipeline(
    display_name: str,
    url: str,
    on_progress,
) -> RecrawlResponse:
    result = await recrawl_domain(
        display_name, url, mark_unviewed=False, on_progress=on_progress
    )
    updated = get_stored_scan(display_name)
    if not updated:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    return _to_recrawl_response(
        updated,
        content_changed=result.content_changed,
        regenerated=result.regenerated,
    )


async def _run_generate_pipeline(
    url: str,
    on_progress,
) -> GenerateResponse:
    scan = await run_scan(url, on_progress=on_progress)
    pages = scan.crawl.pages
    llms_txt, pages_included = await build_llms_txt(pages, on_progress=on_progress)
    hostname = urlparse(url).hostname or ""
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


@app.post("/scans/{domain}/recrawl/stream")
async def recrawl_stream(domain: str):
    display_name = _normalize_domain_param(domain)
    stored = get_stored_scan(display_name)
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    url = stored["url"]

    async def run(on_progress):
        return await _run_recrawl_pipeline(display_name, url, on_progress)

    return _sse_streaming_response(run)


@app.post("/scans/{domain}/refresh/stream")
async def refresh_stream(domain: str):
    return await recrawl_stream(domain)


@app.post("/scans/{domain}/recrawl", response_model=RecrawlResponse)
async def recrawl_scan(domain: str):
    display_name = _normalize_domain_param(domain)
    stored = get_stored_scan(display_name)
    if not stored:
        raise HTTPException(status_code=404, detail="No scan found for this domain.")

    try:
        result = await recrawl_domain(display_name, stored["url"], mark_unviewed=False)
    except ScanError as exc:
        _raise_scan_error(exc)

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
    try:
        return await _run_generate_pipeline(str(request.url), on_progress=None)
    except ScanError as exc:
        _raise_scan_error(exc)


@app.post("/generate/stream")
async def generate_stream(request: CrawlRequest):
    async def run(on_progress):
        return await _run_generate_pipeline(str(request.url), on_progress)

    return _sse_streaming_response(run)
