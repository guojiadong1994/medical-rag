import { USE_MOCK, apiRequest } from './client'
import { mockAsk } from '@/mocks/rag'
import type { ChatMessage, PatientDetail } from '@/types'

export async function askMedicalKnowledge(patient: PatientDetail, question: string): Promise<ChatMessage> {
  if (USE_MOCK) return mockAsk(patient, question)

  return apiRequest<ChatMessage>('/rag/ask', {
    method: 'POST',
    body: JSON.stringify({ patientId: patient.id, question }),
  })
}
