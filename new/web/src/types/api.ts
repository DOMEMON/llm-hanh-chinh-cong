export type Citation = {
  claim_text: string
  fragment_id: string
  source_id: string
  source_locator: string
}

export type GroundedAnswer = {
  status: 'answered' | 'clarification_needed' | 'insufficient_data'
  answer_text: string
  clarification_prompt?: string | null
  citations: Citation[]
  evidence_bundle_id: string
  created_at: string
}

export type AnswerResponse = {
  answer: GroundedAnswer
  sessionId: string | null
}

export type ChatTurn = {
  id: string
  question: string
  answer: GroundedAnswer
}
