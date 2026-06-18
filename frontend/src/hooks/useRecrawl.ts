import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { consumeProgressStream } from '../lib/consumeProgressStream'
import { mapScanResponse, type AnalysisData } from '../types/analysis'
import { type GenerateProgress, type GenerationStepId } from '../types/generation'
import { recentScansQueryKey } from './useRecentScans'
import { scanQueryKey } from './useScan'

const API_URL = import.meta.env.VITE_API_URL

export interface RecrawlResult extends AnalysisData {
  contentChanged: boolean
  regenerated: boolean
}

function mapRecrawlResponse(data: Record<string, unknown>): RecrawlResult {
  return {
    ...mapScanResponse(data),
    contentChanged: Boolean(data.content_changed),
    regenerated: Boolean(data.regenerated),
  }
}

async function recrawlWithStream(
  domain: string,
  onProgress: (progress: GenerateProgress) => void,
): Promise<RecrawlResult> {
  const response = await fetch(
    `${API_URL}/scans/${encodeURIComponent(domain)}/recrawl/stream`,
    { method: 'POST' },
  )

  return consumeProgressStream(response, onProgress, mapRecrawlResponse, {
    missingResultMessage: 'Rescan finished without a result.',
  })
}

export function useRecrawl(domain: string | undefined) {
  const queryClient = useQueryClient()
  const [progress, setProgress] = useState<GenerateProgress | null>(null)

  const mutation = useMutation({
    mutationFn: async (): Promise<RecrawlResult> => {
      setProgress({ step: 'checking_access' satisfies GenerationStepId })
      return recrawlWithStream(domain!, setProgress)
    },
    onSuccess: (result) => {
      queryClient.setQueryData(scanQueryKey(domain ?? ''), result)
      queryClient.invalidateQueries({ queryKey: recentScansQueryKey })
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
