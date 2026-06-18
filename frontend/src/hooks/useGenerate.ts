import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { consumeProgressStream } from '../lib/consumeProgressStream'
import { mapGenerateResponse, type AnalysisData } from '../types/analysis'
import {
  type GenerateProgress,
  type GenerationStepId,
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

  return consumeProgressStream(response, onProgress, mapGenerateResponse, {
    invalidUrlMessage: 'Please enter a valid URL starting with http:// or https://',
    missingResultMessage: 'Generation finished without a result.',
  })
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
