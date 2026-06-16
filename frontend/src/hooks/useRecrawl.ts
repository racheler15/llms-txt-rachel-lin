import { useMutation, useQueryClient } from '@tanstack/react-query'
import { mapScanResponse, type AnalysisData } from '../types/analysis'
import { parseApiError } from '../types/errors'
import { recentScansQueryKey } from './useRecentScans'
import { scanQueryKey } from './useScan'

const API_URL = import.meta.env.VITE_API_URL

export interface RecrawlResult extends AnalysisData {
  contentChanged: boolean
  regenerated: boolean
}

export function useRecrawl(domain: string | undefined) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<RecrawlResult> => {
      const response = await fetch(`${API_URL}/scans/${encodeURIComponent(domain!)}/recrawl`, {
        method: 'POST',
      })

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw parseApiError(body, `Server returned ${response.status}`)
      }

      const data = await response.json()
      return {
        ...mapScanResponse(data),
        contentChanged: Boolean(data.content_changed),
        regenerated: Boolean(data.regenerated),
      }
    },
    onSuccess: (result) => {
      queryClient.setQueryData(scanQueryKey(domain ?? ''), result)
      queryClient.invalidateQueries({ queryKey: recentScansQueryKey })
    },
  })
}
