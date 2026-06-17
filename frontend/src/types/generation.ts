export const GENERATION_STEPS = [
  { id: 'checking_access', label: 'Checking site access' },
  { id: 'discovering_pages', label: 'Discovering pages' },
  { id: 'crawling', label: 'Crawling pages' },
  { id: 'analyzing_readiness', label: 'Analyzing AI readiness' },
  { id: 'generating', label: 'Generating llms.txt' },
] as const

export type GenerationStepId = (typeof GENERATION_STEPS)[number]['id']

export interface GenerateProgress {
  step: GenerationStepId
  pagesCrawled?: number
}

export function isGenerationStepId(value: string): value is GenerationStepId {
  return GENERATION_STEPS.some((step) => step.id === value)
}
