import { API_BASE_URL, USE_MOCK, apiRequest } from './client'
import { mockDoctor } from '@/mocks/data'
import type { DoctorProfile } from '@/types'

export interface LoginResponse {
  accessToken: string
  doctor: DoctorProfile
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 450))
    if (username !== 'doctor' || password !== '123456') {
      throw new Error('账号或密码错误')
    }
    return { accessToken: 'mock-doctor-token', doctor: mockDoctor }
  }

  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export { API_BASE_URL }
