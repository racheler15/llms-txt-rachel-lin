import { useQuery } from '@tanstack/react-query'

const API_URL = import.meta.env.VITE_API_URL

export interface RecentScan {
  domain: string
  url: string
  pagesCrawled: number
  pagesIncluded: number
  readinessTotal: number
  hasContentChanges: boolean
  hasUnviewedChanges: boolean
  lastScannedAt: string
  generated: boolean
}

export const recentScansQueryKey = ['scans'] as const

function mapRecentScan(data: Record<string, unknown>): RecentScan {
  return {
    domain: data.domain as string,
    url: data.url as string,
    pagesCrawled: data.pages_crawled as number,
    pagesIncluded: data.pages_included as number,
    readinessTotal: data.readiness_total as number,
    hasContentChanges: Boolean(data.has_content_changes),
    hasUnviewedChanges: Boolean(data.has_unviewed_changes),
    lastScannedAt: data.last_scanned_at as string,
    generated: Boolean(data.generated),
  }
}

export function useRecentScans() {
  return useQuery({
    queryKey: recentScansQueryKey,
    queryFn: async (): Promise<RecentScan[]> => {
      const response = await fetch(`${API_URL}/scans`)

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const message = typeof body?.detail === 'string' ? body.detail : `Server returned ${response.status}`
        throw new Error(message)
      }

      const data = await response.json()
      return (data as Record<string, unknown>[]).map(mapRecentScan)
    },
  })
}
