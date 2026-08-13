import { apiRequest } from './client'
import type { PatientDetail, PatientSummary } from '@/types'

export function fetchPatients(): Promise<PatientSummary[]> {
  return apiRequest<PatientSummary[]>('/patients')
}

export function fetchPatientDetail(id: string): Promise<PatientDetail> {
  return apiRequest<PatientDetail>(`/patients/${id}`)
}
