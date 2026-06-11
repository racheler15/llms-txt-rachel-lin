from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crawler import Page, crawl_site
from generator import categorize_pages, generate_llms_txt


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL. Must be a valid http or https URL.")
    return url

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CrawlRequest(BaseModel):
    url: str


class GenerateResponse(BaseModel):
    llms_txt: str


@app.post("/crawl", response_model=list[Page])
def crawl(request: CrawlRequest):
    _validate_url(request.url)
    return crawl_site(request.url)


@app.post("/generate", response_model=GenerateResponse)
def generate(request: CrawlRequest):
    _validate_url(request.url)
    pages = crawl_site(request.url)
    if not pages:
        raise HTTPException(status_code=404, detail="No pages could be crawled from this site.")

    categorized = categorize_pages(pages)
    llms_txt = generate_llms_txt(pages, categorized)

    return GenerateResponse(llms_txt=llms_txt)
