export function extractHostnameFromLlmsTxt(llmsTxt: string): string {
  const match = llmsTxt.match(/\]\((https?:\/\/[^)]+)\)/)
  if (!match) return ''

  try {
    return new URL(match[1]).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

export function parseLlmsTxtStats(llmsTxt: string) {
  const categoryCount = (llmsTxt.match(/^## /gm) ?? []).length
  const pagesIncluded = (llmsTxt.match(/^- \[/gm) ?? []).length

  return { pagesIncluded, categoryCount }
}

export interface CategoryLink {
  title: string
  url: string
  description?: string
}

export interface LlmsTxtCategory {
  name: string
  count: number
  links: CategoryLink[]
}

const LLMS_LINK_PATTERN = /^- \[([^\]]+)\]\(([^)]+)\)(?::\s*(.*))?$/

export function parseLlmsTxtCategories(llmsTxt: string): LlmsTxtCategory[] {
  const categories: LlmsTxtCategory[] = []
  const lines = llmsTxt.split('\n')
  let current: LlmsTxtCategory | null = null

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (current) {
        categories.push(current)
      }
      current = { name: line.slice(3).trim(), count: 0, links: [] }
      continue
    }

    if (!current) {
      continue
    }

    const match = line.match(LLMS_LINK_PATTERN)
    if (match) {
      current.links.push({
        title: match[1],
        url: match[2],
        description: match[3]?.trim() || undefined,
      })
      current.count += 1
    }
  }

  if (current) {
    categories.push(current)
  }

  return categories
}

export function formatScannedLabel(iso: string): string {
  const scannedAt = new Date(iso)
  if (Number.isNaN(scannedAt.getTime())) {
    return 'scanned recently'
  }

  const diffMs = Date.now() - scannedAt.getTime()
  const diffMinutes = Math.floor(diffMs / 60_000)

  if (diffMinutes < 1) {
    return 'scanned just now'
  }
  if (diffMinutes < 60) {
    return `scanned ${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`
  }

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) {
    return `scanned ${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  }

  const diffDays = Math.floor(diffHours / 24)
  return `scanned ${diffDays} day${diffDays === 1 ? '' : 's'} ago`
}
