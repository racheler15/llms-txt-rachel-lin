import { useMutation, useQueryClient } from '@tanstack/react-query'
import { mapScanResponse, type AnalysisData } from '../types/analysis'
import { recentScansQueryKey } from './useRecentScans'
import { scanQueryKey } from './useScan'

const API_URL = import.meta.env.VITE_API_URL

export function useMarkViewed(domain: string | undefined) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (): Promise<AnalysisData> => {
      const response = await fetch(`${API_URL}/scans/${encodeURIComponent(domain!)}/mark-viewed`, {
        method: 'POST',
      })

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        const message = typeof body?.detail === 'string' ? body.detail : `Server returned ${response.status}`
        throw new Error(message)
      }

      const data = await response.json()
      return mapScanResponse(data)
    },
    onSuccess: (result) => {
      queryClient.setQueryData(scanQueryKey(domain ?? ''), result)
      queryClient.invalidateQueries({ queryKey: recentScansQueryKey })
    },
  })
}
