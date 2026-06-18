import { parseApiError } from '../types/errors'
import { type GenerateProgress, isGenerationStepId } from '../types/generation'

interface SseEvent {
  event: string
  data: Record<string, unknown>
}

interface ConsumeProgressStreamOptions {
  invalidUrlMessage?: string
  missingResultMessage?: string
}

async function* readSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)

        let event = 'message'
        let data = ''

        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('event:')) {
            event = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            data += line.slice(5).trim()
          }
        }

        if (data) {
          yield {
            event,
            data: JSON.parse(data) as Record<string, unknown>,
          }
        }

        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function consumeProgressStream<T>(
  response: Response,
  onProgress: (progress: GenerateProgress) => void,
  mapComplete: (data: Record<string, unknown>) => T,
  options: ConsumeProgressStreamOptions = {},
): Promise<T> {
  if (!response.ok) {
    if (response.status === 422 && options.invalidUrlMessage) {
      throw new Error(options.invalidUrlMessage)
    }
    const body = await response.json().catch(() => null)
    throw parseApiError(body, `Server returned ${response.status}`)
  }

  if (!response.body) {
    throw new Error('No response body received from server.')
  }

  let result: T | null = null

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
      result = mapComplete(sseEvent.data)
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
    throw new Error(options.missingResultMessage ?? 'Request finished without a result.')
  }

  return result
}
