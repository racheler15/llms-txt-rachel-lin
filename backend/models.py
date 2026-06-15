from pydantic import BaseModel, HttpUrl


class Page(BaseModel):
    url: str
    title: str
    description: str
    h1: str
    og_type: str
    depth: int
    content_hash: str
    meta_description: str = ""
    word_count: int = 0
    in_sitemap: bool = False
    sitemap_priority: float | None = None
    inbound_count: int = 0


class CrawlRequest(BaseModel):
    url: HttpUrl


class ReadinessCategoryResponse(BaseModel):
    id: str
    score: int
    max_score: int
    label: str


class ReadinessResponse(BaseModel):
    total: int
    max_total: int = 100
    categories: list[ReadinessCategoryResponse]
    recommendations: list[str]


class GenerateResponse(BaseModel):
    llms_txt: str
    domain: str
    pages_crawled: int
    pages_included: int
    readiness: ReadinessResponse
