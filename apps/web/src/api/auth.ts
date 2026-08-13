import { apiRequest } from './client'
import type { DoctorProfile } from '@/types'

interface LoginResponse {
  accessToken: string
  doctor: DoctorProfile
}

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}
