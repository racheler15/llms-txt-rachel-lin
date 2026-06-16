import { useQuery, useQueryClient } from '@tanstack/react-query'
import { mapScanResponse, type AnalysisData } from '../types/analysis'

const API_URL = import.meta.env.VITE_API_URL

export function scanQueryKey(domain: string) {
  return ['scan', domain] as const
}

export function useScan(domain: string | undefined) {
  return useQuery({
    queryKey: scanQueryKey(domain ?? ''),
    queryFn: async (): Promise<AnalysisData> => {
      const response = await fetch(`${API_URL}/scans/${encodeURIComponent(domain!)}`)

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('No analysis found for this domain. Generate one from the homepage.')
        }
        const body = await response.json().catch(() => null)
        const message = typeof body?.detail === 'string' ? body.detail : `Server returned ${response.status}`
        throw new Error(message)
      }

      const data = await response.json()
      return mapScanResponse(data)
    },
    enabled: Boolean(domain),
  })
}

export function useSeedScanCache() {
  const queryClient = useQueryClient()

  return (data: AnalysisData) => {
    queryClient.setQueryData(scanQueryKey(data.domain), data)
  }
}
