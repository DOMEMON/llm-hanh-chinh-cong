import type { AnswerResponse, GroundedAnswer } from '../types/api'

type ErrorResponse = {
  detail?: string | { msg?: string }[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '::1'])

export function resolveApiBaseUrl(configuredValue: string, pageUrl: string) {
  const configured = new URL(configuredValue)
  const page = new URL(pageUrl)
  if (
    LOOPBACK_HOSTS.has(configured.hostname) &&
    LOOPBACK_HOSTS.has(page.hostname) &&
    configured.hostname !== page.hostname
  ) {
    configured.hostname = page.hostname
  }
  return configured.toString().replace(/\/$/, '')
}

function getApiBaseUrl() {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/$/, '')
  if (!apiBaseUrl) {
    throw new Error('Thiếu VITE_API_BASE_URL. Hãy cấu hình URL của Backend.')
  }
  return resolveApiBaseUrl(apiBaseUrl, window.location.href)
}

export async function answerQuestion(
  query: string,
  sessionId: string,
): Promise<AnswerResponse> {
  let response: Response
  try {
    response = await fetch(`${getApiBaseUrl()}/answer`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query_text_raw: query,
        session_id: sessionId,
      }),
    })
  } catch (requestError) {
    if (requestError instanceof DOMException && requestError.name === 'AbortError') {
      throw requestError
    }
    throw new Error('Không kết nối được Backend. Hãy kiểm tra backend và CORS.', {
      cause: requestError,
    })
  }

  if (!response.ok) {
    let message = `Backend trả về lỗi HTTP ${response.status}.`
    try {
      const body = (await response.json()) as ErrorResponse
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) {
        message = body.detail.map(({ msg }) => msg).filter(Boolean).join('; ') || message
      }
    } catch {
      // Keep the explicit HTTP status when the backend does not return JSON.
    }
    throw new ApiError(message, response.status)
  }

  const answer = (await response.json()) as GroundedAnswer
  return {
    answer,
    sessionId: response.headers.get('X-Conversation-Session-Id'),
  }
}
