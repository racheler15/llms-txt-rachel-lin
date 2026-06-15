import { useMutation } from '@tanstack/react-query'

const GENERATE_API_URL = `${import.meta.env.VITE_API_URL}/generate`

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
}

export interface GenerateResult {
  llmsTxt: string
  domain: string
  pagesCrawled: number
  pagesIncluded: number
  readiness: ReadinessResult
}

function mapReadinessResult(raw: Record<string, unknown>): ReadinessResult {
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
  }
}

export function useGenerate() {
  return useMutation({
    mutationFn: async (url: string): Promise<GenerateResult> => {
      const response = await fetch(GENERATE_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        if (response.status === 422) {
          throw new Error('Please enter a valid URL starting with http:// or https://')
        }
        const body = await response.json().catch(() => null)
        const message = typeof body?.detail === 'string' ? body.detail : `Server returned ${response.status}`
        throw new Error(message)
      }

      const data = await response.json()
      return {
        llmsTxt: data.llms_txt,
        domain: data.domain,
        pagesCrawled: data.pages_crawled,
        pagesIncluded: data.pages_included,
        readiness: mapReadinessResult(data.readiness),
      }
    },
  })
}
