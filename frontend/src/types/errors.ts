export type ScanErrorType = 'timeout' | 'robots_blocked' | 'no_pages'

interface ApiErrorBody {
  detail?: string | { message?: string; error_type?: ScanErrorType }
}

export function parseApiError(body: unknown, fallback: string): Error {
  if (!body || typeof body !== 'object') {
    return new Error(fallback)
  }

  const detail = (body as ApiErrorBody).detail
  if (typeof detail === 'string') {
    return new Error(detail)
  }

  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return new Error(detail.message)
  }

  return new Error(fallback)
}
