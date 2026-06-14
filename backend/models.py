from pydantic import BaseModel, HttpUrl


class Page(BaseModel):
    url: str
    title: str
    description: str
    h1: str
    og_type: str
    depth: int
    content_hash: str
    in_sitemap: bool = False
    sitemap_priority: float | None = None
    inbound_count: int = 0


class CrawlRequest(BaseModel):
    url: HttpUrl


class GenerateResponse(BaseModel):
    llms_txt: str
