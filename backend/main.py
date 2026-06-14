from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging

from crawler import crawl_site
from generator import categorize_pages, generate_llms_txt
from models import CrawlRequest, GenerateResponse, Page

logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/crawl", response_model=list[Page])
async def crawl(request: CrawlRequest):
    return await crawl_site(str(request.url))


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: CrawlRequest):
    pages = await crawl_site(str(request.url))
    if not pages:
        raise HTTPException(status_code=404, detail="No pages could be crawled from this site.")

    categorized = categorize_pages(pages)
    llms_txt = generate_llms_txt(pages, categorized)

    return GenerateResponse(llms_txt=llms_txt)
