import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { answerQuestion, ApiError, resolveApiBaseUrl } from './api'

describe('Backend API client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:8000/api/v1/')
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
  })

  it('keeps loopback API calls on the same host as the opened page', () => {
    expect(
      resolveApiBaseUrl('http://localhost:8000/api/v1/', 'http://127.0.0.1:3000/'),
    ).toBe('http://127.0.0.1:8000/api/v1')
  })

  it('sends the new backend answer contract and returns its session header', async () => {
    const answer = {
      status: 'answered' as const,
      answer_text: 'Câu trả lời mô phỏng.',
      citations: [],
      evidence_bundle_id: 'bundle-1',
      created_at: '2026-10-22T01:00:00Z',
    }
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(answer), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'X-Conversation-Session-Id': 'session-1',
        },
      }),
    )

    await expect(answerQuestion('Câu hỏi thử', 'session-1')).resolves.toEqual({
      answer,
      sessionId: 'session-1',
    })

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/answer')
    expect(options.method).toBe('POST')
    expect(options.credentials).toBe('include')
    expect(JSON.parse(options.body as string)).toEqual({
      query_text_raw: 'Câu hỏi thử',
      session_id: 'session-1',
    })
  })

  it('exposes backend validation errors and status codes', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'No active corpus; import one first' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(answerQuestion('Câu hỏi thử', 'session-1')).rejects.toMatchObject({
      message: 'No active corpus; import one first',
      status: 503,
    } satisfies Partial<ApiError>)
  })

  it('reports connection failures with local backend guidance', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))

    await expect(answerQuestion('Câu hỏi thử', 'session-1')).rejects.toThrow(
      'Không kết nối được Backend. Hãy kiểm tra backend và CORS.',
    )
  })
})
