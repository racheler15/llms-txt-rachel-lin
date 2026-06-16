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
    has_content_changes: bool = False
    has_unviewed_changes: bool = False


class ScanResponse(BaseModel):
    domain: str
    url: str
    llms_txt: str | None = None
    pages_crawled: int
    pages_included: int
    readiness: ReadinessResponse
    has_content_changes: bool = False
    has_unviewed_changes: bool = False
    last_scanned_at: str


class RecrawlResponse(BaseModel):
    domain: str
    url: str
    pages_crawled: int
    pages_included: int
    readiness: ReadinessResponse
    has_content_changes: bool = False
    has_unviewed_changes: bool = False
    last_scanned_at: str
    llms_txt: str | None = None
    content_changed: bool = False
    regenerated: bool = False


class ScanSummaryResponse(BaseModel):
    domain: str
    url: str
    pages_crawled: int
    pages_included: int
    readiness_total: int
    has_content_changes: bool = False
    has_unviewed_changes: bool = False
    last_scanned_at: str
    generated: bool = False
