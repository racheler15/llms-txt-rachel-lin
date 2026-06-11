import { useMutation } from '@tanstack/react-query'

const GENERATE_API_URL = `${import.meta.env.VITE_API_URL}/generate`

export function useGenerate() {
  return useMutation({
    mutationFn: async (url: string): Promise<string> => {
      const response = await fetch(GENERATE_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail ?? `Server returned ${response.status}`)
      }

      const data = await response.json()
      return data.llms_txt
    },
  })
}
