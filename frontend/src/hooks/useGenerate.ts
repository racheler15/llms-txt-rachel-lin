import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { readSseStream } from '../lib/readSseStream'
import { mapGenerateResponse, type AnalysisData } from '../types/analysis'
import { parseApiError } from '../types/errors'
import {
  type GenerateProgress,
  type GenerationStepId,
  isGenerationStepId,
} from '../types/generation'

const GENERATE_STREAM_URL = `${import.meta.env.VITE_API_URL}/generate/stream`

async function generateWithStream(
  url: string,
  onProgress: (progress: GenerateProgress) => void,
): Promise<AnalysisData> {
  const response = await fetch(GENERATE_STREAM_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })

  if (!response.ok) {
    if (response.status === 422) {
      throw new Error('Please enter a valid URL starting with http:// or https://')
    }
    const body = await response.json().catch(() => null)
    throw parseApiError(body, `Server returned ${response.status}`)
  }

  if (!response.body) {
    throw new Error('No response body received from server.')
  }

  let result: AnalysisData | null = null

  for await (const sseEvent of readSseStream(response.body)) {
    if (sseEvent.event === 'stage') {
      const step = sseEvent.data.step
      if (typeof step === 'string' && isGenerationStepId(step)) {
        onProgress({ step })
      }
      continue
    }

    if (sseEvent.event === 'progress') {
      const step = sseEvent.data.step
      if (typeof step === 'string' && isGenerationStepId(step)) {
        onProgress({
          step,
          pagesCrawled:
            typeof sseEvent.data.pages_crawled === 'number'
              ? sseEvent.data.pages_crawled
              : undefined,
        })
      }
      continue
    }

    if (sseEvent.event === 'complete') {
      result = mapGenerateResponse(sseEvent.data)
      continue
    }

    if (sseEvent.event === 'error') {
      const message =
        typeof sseEvent.data.message === 'string'
          ? sseEvent.data.message
          : 'Something went wrong. Please try again.'
      throw new Error(message)
    }
  }

  if (!result) {
    throw new Error('Generation finished without a result.')
  }

  return result
}

export function useGenerate() {
  const [progress, setProgress] = useState<GenerateProgress | null>(null)

  const mutation = useMutation({
    mutationFn: async (url: string) => {
      setProgress({ step: 'checking_access' satisfies GenerationStepId })
      return generateWithStream(url, setProgress)
    },
    onSettled: () => {
      setProgress(null)
    },
  })

  return {
    ...mutation,
    progress,
  }
}
