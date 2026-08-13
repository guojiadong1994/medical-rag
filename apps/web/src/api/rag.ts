import { apiRequest } from './client'
import type { ChatMessage } from '@/types'

export function askMedicalKnowledge(patientId: string, question: string): Promise<ChatMessage> {
  return apiRequest<ChatMessage>('/rag/ask', {
    method: 'POST',
    body: JSON.stringify({ patientId, question }),
  })
}

export function askKnowledge(question: string): Promise<ChatMessage> {
  return apiRequest<ChatMessage>('/rag/ask', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}
