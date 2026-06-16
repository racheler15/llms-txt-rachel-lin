import { useMutation } from '@tanstack/react-query'
import { mapGenerateResponse, type AnalysisData } from '../types/analysis'

const GENERATE_API_URL = `${import.meta.env.VITE_API_URL}/generate`

export function useGenerate() {
  return useMutation({
    mutationFn: async (url: string): Promise<AnalysisData> => {
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
      return mapGenerateResponse(data)
    },
  })
}
