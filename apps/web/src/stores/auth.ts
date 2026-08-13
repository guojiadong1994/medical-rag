import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi } from '@/api/auth'
import type { DoctorProfile } from '@/types'

const TOKEN_KEY = 'medical-rag-token'
const DOCTOR_KEY = 'medical-rag-doctor'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) ?? '')
  const doctor = ref<DoctorProfile | null>(JSON.parse(localStorage.getItem(DOCTOR_KEY) || 'null'))
  const isLoggedIn = computed(() => Boolean(token.value))

  async function login(username: string, password: string) {
    const result = await loginApi(username, password)
    token.value = result.accessToken
    doctor.value = result.doctor
    localStorage.setItem(TOKEN_KEY, result.accessToken)
    localStorage.setItem(DOCTOR_KEY, JSON.stringify(result.doctor))
  }

  function logout() {
    token.value = ''
    doctor.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(DOCTOR_KEY)
  }

  return { token, doctor, isLoggedIn, login, logout }
})
