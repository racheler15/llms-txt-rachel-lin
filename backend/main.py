from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
from urllib.parse import urlparse

from generator import categorize_pages, generate_llms_txt
from models import (
    CrawlRequest,
    GenerateResponse,
    ReadinessCategoryResponse,
    ReadinessResponse,
)
from readiness import ReadinessResult
from scan import run_scan
from url_utils import display_domain

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: CrawlRequest):
    scan = await run_scan(str(request.url))
    pages = scan.crawl.pages
    if not pages:
        raise HTTPException(status_code=404, detail="No pages could be crawled from this site.")

    categorized = await categorize_pages(pages)
    llms_txt, pages_included = await generate_llms_txt(pages, categorized)
    hostname = urlparse(str(request.url)).hostname or ""
    domain = display_domain(hostname)

    return GenerateResponse(
        llms_txt=llms_txt,
        domain=domain,
        pages_crawled=len(pages),
        pages_included=pages_included,
        readiness=_to_readiness_response(scan.readiness),
    )
