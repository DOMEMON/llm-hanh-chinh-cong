import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'
import { answerQuestion } from './services/api'
import type { ChatTurn, GroundedAnswer } from './types/api'

const SESSION_ID_KEY = 'rag-chat-session-id'
const HISTORY_KEY = 'rag-chat-history'
const MAX_QUESTION_LENGTH = 4000

function isChatTurn(value: unknown): value is ChatTurn {
  if (!value || typeof value !== 'object') return false
  const turn = value as Partial<ChatTurn>
  return (
    typeof turn.id === 'string' &&
    typeof turn.question === 'string' &&
    Boolean(turn.answer) &&
    typeof turn.answer?.answer_text === 'string' &&
    Array.isArray(turn.answer?.citations)
  )
}

function newSessionId() {
  return crypto.randomUUID()
}

function readInitialState() {
  let initialSessionId: string
  let initialMessages: ChatTurn[] = []
  let initialError = ''

  try {
    initialSessionId = sessionStorage.getItem(SESSION_ID_KEY) ?? ''
    if (!/^[A-Za-z0-9_-]{1,100}$/.test(initialSessionId)) {
      initialSessionId = newSessionId()
      sessionStorage.setItem(SESSION_ID_KEY, initialSessionId)
    }
  } catch {
    initialSessionId = newSessionId()
    initialError = 'Không thể lưu mã phiên làm việc vào trình duyệt.'
  }

  try {
    const savedHistory = sessionStorage.getItem(HISTORY_KEY)
    if (savedHistory) {
      const parsed: unknown = JSON.parse(savedHistory)
      if (!Array.isArray(parsed) || !parsed.every(isChatTurn)) {
        throw new Error('Dữ liệu lịch sử không đúng định dạng.')
      }
      initialMessages = parsed
    }
  } catch {
    initialError = 'Không thể khôi phục lịch sử phiên này từ trình duyệt.'
  }

  return { sessionId: initialSessionId, messages: initialMessages, error: initialError }
}

function statusLabel(status: GroundedAnswer['status']) {
  switch (status) {
    case 'answered':
      return 'Có câu trả lời trích xuất'
    case 'clarification_needed':
      return 'Cần làm rõ câu hỏi'
    case 'insufficient_data':
      return 'Chưa đủ dữ liệu'
  }
}

function AnswerCard({ answer }: { answer: GroundedAnswer }) {
  const content =
    answer.answer_text ||
    answer.clarification_prompt ||
    'Không có đủ bằng chứng để tạo câu trả lời.'

  return (
    <section className={`answer-card answer-${answer.status}`} aria-label="Phản hồi">
      <div className="answer-status">{statusLabel(answer.status)}</div>
      <p className="answer-text">{content}</p>
      {answer.citations.length > 0 && (
        <details className="citations">
          <summary>Nguồn trích dẫn ({answer.citations.length})</summary>
          <ol>
            {answer.citations.map((citation) => (
              <li key={`${citation.fragment_id}-${citation.source_id}`}>
                <p>{citation.claim_text}</p>
                <code>
                  {citation.source_id} · {citation.fragment_id}
                  {citation.source_locator && ` · ${citation.source_locator}`}
                </code>
              </li>
            ))}
          </ol>
        </details>
      )}
      <small className="bundle-id">Evidence: {answer.evidence_bundle_id}</small>
    </section>
  )
}

function App() {
  const [initialState] = useState(readInitialState)
  const [sessionId, setSessionId] = useState(initialState.sessionId)
  const [messages, setMessages] = useState<ChatTurn[]>(initialState.messages)
  const [question, setQuestion] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [error, setError] = useState(initialState.error)
  const endOfMessagesRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView?.({ block: 'end' })
  }, [messages, pendingQuestion])

  function saveHistory(turns: ChatTurn[]) {
    setMessages(turns)
    try {
      sessionStorage.setItem(HISTORY_KEY, JSON.stringify(turns))
    } catch {
      setError('Lịch sử đang hiển thị nhưng không thể lưu vào phiên trình duyệt này.')
    }
  }

  function startNewSession() {
    const nextSessionId = newSessionId()
    setSessionId(nextSessionId)
    setQuestion('')
    setError('')
    saveHistory([])
    try {
      sessionStorage.setItem(SESSION_ID_KEY, nextSessionId)
    } catch {
      setError('Không thể lưu phiên mới vào trình duyệt.')
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const normalizedQuestion = question.trim()
    if (!normalizedQuestion || !sessionId || pendingQuestion) return

    setPendingQuestion(normalizedQuestion)
    setError('')
    try {
      const result = await answerQuestion(normalizedQuestion, sessionId)
      const turn: ChatTurn = {
        id: crypto.randomUUID(),
        question: normalizedQuestion,
        answer: result.answer,
      }
      saveHistory([...messages, turn])
      setQuestion('')
      if (result.sessionId && result.sessionId !== sessionId) {
        setSessionId(result.sessionId)
        try {
          sessionStorage.setItem(SESSION_ID_KEY, result.sessionId)
        } catch {
          setError('Không thể lưu mã phiên làm việc vào trình duyệt.')
        }
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'Không thể gửi câu hỏi. Vui lòng thử lại.',
      )
    } finally {
      setPendingQuestion('')
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand">
          <p className="eyebrow">BẢN THỬ NGHIỆM · RETRIEVAL</p>
          <h1>Trợ lý thủ tục hành chính</h1>
        </div>
        <button className="new-session" type="button" onClick={startNewSession}>
          Cuộc trò chuyện mới
        </button>
      </header>

      <aside className="demo-notice" role="note">
        Corpus hiện ở trạng thái nháp. Câu trả lời do mô hình tạo có thể sai; hãy
        đối chiếu nguồn và không coi đây là tư vấn pháp lý đã xác minh.
      </aside>

      {error && (
        <div className="error-banner" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError('')} aria-label="Đóng thông báo lỗi">
            Đóng
          </button>
        </div>
      )}

      <section className="chat-panel" aria-label="Hội thoại">
        <div className="messages" aria-live="polite">
          {messages.length === 0 && !pendingQuestion ? (
            <div className="empty-state">
              <span className="empty-mark" aria-hidden="true">H</span>
              <h2>Bạn muốn tìm hiểu thủ tục nào?</h2>
              <p>
                Hãy hỏi về thành phần hồ sơ, thời hạn hoặc lệ phí trong dữ liệu
                thử nghiệm.
              </p>
              <p className="example-question">
                Ví dụ: “Thủ tục đăng ký khai sinh cần những giấy tờ gì?”
              </p>
            </div>
          ) : (
            <>
              {messages.map((turn) => (
                <article className="turn" key={turn.id}>
                  <div className="question-bubble">{turn.question}</div>
                  <AnswerCard answer={turn.answer} />
                </article>
              ))}
              {pendingQuestion && (
                <article className="turn">
                  <div className="question-bubble">{pendingQuestion}</div>
                  <p className="pending-message">Đang tìm bằng chứng trong corpus...</p>
                </article>
              )}
            </>
          )}
          <div ref={endOfMessagesRef} />
        </div>

        <form className="composer" onSubmit={submitQuestion}>
          <label className="visually-hidden" htmlFor="question">
            Nội dung câu hỏi
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Nhập câu hỏi về thủ tục hành chính..."
            maxLength={MAX_QUESTION_LENGTH}
            rows={2}
            disabled={!sessionId || Boolean(pendingQuestion)}
          />
          <div className="composer-footer">
            <span>{question.length}/{MAX_QUESTION_LENGTH}</span>
            <button
              type="submit"
              disabled={!sessionId || !question.trim() || Boolean(pendingQuestion)}
            >
              {pendingQuestion ? 'Đang xử lý...' : 'Gửi câu hỏi'}
            </button>
          </div>
        </form>
      </section>

      <footer className="app-footer">
        Lịch sử chỉ lưu trong tab trình duyệt này; backend chỉ lưu trạng thái
        follow-up và metadata truy vấn.
      </footer>
    </main>
  )
}

export default App
