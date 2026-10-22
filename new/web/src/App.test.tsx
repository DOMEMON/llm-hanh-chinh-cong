import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './services/api'
import type { GroundedAnswer } from './types/api'

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/api')>()
  return { ...actual, answerQuestion: vi.fn() }
})

const answerQuestionMock = vi.mocked(api.answerQuestion)
const answer: GroundedAnswer = {
  status: 'answered',
  answer_text: 'Thành phần hồ sơ theo dữ liệu thử nghiệm.',
  citations: [
    {
      claim_text: 'Thành phần hồ sơ theo dữ liệu thử nghiệm.',
      fragment_id: 'PROC-001-A',
      source_id: 'SRC-001',
      source_locator: 'Sheet1!A1',
    },
  ],
  evidence_bundle_id: 'bundle-001',
  created_at: '2026-10-22T01:00:00Z',
}

describe('retrieval web flow', () => {
  beforeEach(() => {
    sessionStorage.clear()
    sessionStorage.setItem('rag-chat-session-id', 'test-session')
    answerQuestionMock.mockReset()
  })

  it('submits a question and renders the grounded answer and citation', async () => {
    answerQuestionMock.mockResolvedValue({ answer, sessionId: 'test-session' })
    const user = userEvent.setup()

    render(<App />)
    await user.type(
      await screen.findByLabelText('Nội dung câu hỏi'),
      '  Thủ tục đăng ký khai sinh cần giấy tờ gì?  ',
    )
    await user.click(screen.getByRole('button', { name: 'Gửi câu hỏi' }))

    expect(await screen.findAllByText(answer.answer_text)).toHaveLength(2)
    expect(screen.getByText(/SRC-001 · PROC-001-A · Sheet1!A1/)).toBeInTheDocument()
    expect(answerQuestionMock).toHaveBeenCalledWith(
      'Thủ tục đăng ký khai sinh cần giấy tờ gì?',
      'test-session',
    )
    expect(sessionStorage.getItem('rag-chat-history')).toContain(answer.evidence_bundle_id)
    expect(screen.getByLabelText('Nội dung câu hỏi')).toHaveValue('')
  })

  it('retains the question and displays an actionable backend error', async () => {
    answerQuestionMock.mockRejectedValue(new api.ApiError('No active corpus; import one first', 503))
    const user = userEvent.setup()

    render(<App />)
    const input = await screen.findByLabelText('Nội dung câu hỏi')
    await user.type(input, 'Tra cứu thủ tục')
    await user.click(screen.getByRole('button', { name: 'Gửi câu hỏi' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No active corpus; import one first',
    )
    expect(input).toHaveValue('Tra cứu thủ tục')
  })

  it('restores the current tab history and starts a clean session on request', async () => {
    sessionStorage.setItem(
      'rag-chat-history',
      JSON.stringify([{ id: 'turn-1', question: 'Câu hỏi cũ', answer }]),
    )
    const user = userEvent.setup()

    render(<App />)
    expect(await screen.findByText('Câu hỏi cũ')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cuộc trò chuyện mới' }))

    await waitFor(() => expect(screen.queryByText('Câu hỏi cũ')).not.toBeInTheDocument())
    expect(sessionStorage.getItem('rag-chat-history')).toBe('[]')
    expect(sessionStorage.getItem('rag-chat-session-id')).not.toBe('test-session')
  })

  it('shows the draft-corpus and model-answer limitations', async () => {
    render(<App />)

    expect(await screen.findByRole('note')).toHaveTextContent(/Corpus hiện ở trạng thái nháp/)
    expect(screen.getByRole('note')).toHaveTextContent(/Câu trả lời do mô hình tạo có thể sai/)
    expect(screen.getByRole('note')).toHaveTextContent(/không coi đây là tư vấn pháp lý đã xác minh/)
  })
})
