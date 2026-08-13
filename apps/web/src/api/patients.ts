import { USE_MOCK, apiRequest } from './client'
import { getPatientDetail, mockPatients } from '@/mocks/data'
import type { PatientDetail, PatientSummary } from '@/types'

export async function fetchPatients(): Promise<PatientSummary[]> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 250))
    return mockPatients
  }
  return apiRequest<PatientSummary[]>('/patients')
}

export async function fetchPatientDetail(id: string): Promise<PatientDetail> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 180))
    const patient = getPatientDetail(id)
    if (!patient) throw new Error('患者不存在')
    return patient
  }
  return apiRequest<PatientDetail>(`/patients/${id}`)
}
