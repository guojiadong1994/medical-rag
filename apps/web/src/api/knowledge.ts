import { apiRequest } from './client'
import type { KnowledgeDocument } from '@/types'

export function fetchKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  return apiRequest<KnowledgeDocument[]>('/knowledge/documents')
}

export function uploadKnowledgeDocument(file: File): Promise<KnowledgeDocument> {
  const formData = new FormData()
  formData.append('file', file)
  return apiRequest<KnowledgeDocument>('/knowledge/documents', {
    method: 'POST',
    body: formData,
  })
}
