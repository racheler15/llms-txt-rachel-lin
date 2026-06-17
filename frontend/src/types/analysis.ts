export interface ReadinessCategory {
  id: string
  score: number
  max_score: number
  label: string
}

export interface ReadinessResult {
  total: number
  max_total: number
  categories: ReadinessCategory[]
  recommendations: string[]
  js_rendering_likely: boolean
}

export interface AnalysisData {
  llmsTxt: string | null
  domain: string
  url?: string
  pagesCrawled: number
  pagesIncluded: number
  readiness: ReadinessResult
  hasContentChanges: boolean
  hasUnviewedChanges: boolean
  lastScannedAt: string
}

export function mapReadinessResult(raw: Record<string, unknown>): ReadinessResult {
  const rawCategories = (raw.categories as Record<string, unknown>[]) ?? []

  return {
    total: raw.total as number,
    max_total: (raw.max_total as number) ?? 100,
    categories: rawCategories.map((category) => ({
      id: category.id as string,
      score: category.score as number,
      max_score: category.max_score as number,
      label: category.label as string,
    })),
    recommendations: (raw.recommendations as string[]) ?? [],
    js_rendering_likely: Boolean(raw.js_rendering_likely),
  }
}

export function mapScanResponse(data: Record<string, unknown>): AnalysisData {
  return {
    llmsTxt: (data.llms_txt as string | null) ?? null,
    domain: data.domain as string,
    url: data.url as string | undefined,
    pagesCrawled: data.pages_crawled as number,
    pagesIncluded: data.pages_included as number,
    readiness: mapReadinessResult(data.readiness as Record<string, unknown>),
    hasContentChanges: Boolean(data.has_content_changes),
    hasUnviewedChanges: Boolean(data.has_unviewed_changes),
    lastScannedAt: data.last_scanned_at as string,
  }
}

export function mapGenerateResponse(data: Record<string, unknown>): AnalysisData {
  return {
    llmsTxt: data.llms_txt as string,
    domain: data.domain as string,
    pagesCrawled: data.pages_crawled as number,
    pagesIncluded: data.pages_included as number,
    readiness: mapReadinessResult(data.readiness as Record<string, unknown>),
    hasContentChanges: Boolean(data.has_content_changes),
    hasUnviewedChanges: Boolean(data.has_unviewed_changes),
    lastScannedAt: new Date().toISOString(),
  }
}
