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
