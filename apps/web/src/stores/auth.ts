import { defineStore } from 'pinia'

export type UserRole = 'user' | 'admin'

export interface SessionUser {
  id: string
  name: string
  role: UserRole
  account: string
}

const SESSION_KEY = 'medical-rag-session'

export const PRESET_ACCOUNTS = {
  user: {
    account: 'user001',
    password: '123456',
    user: { id: 'U10001', name: '郭嘉栋', role: 'user' as const, account: 'user001' },
  },
  admin: {
    account: 'admin',
    password: 'admin123',
    user: { id: 'A10001', name: '系统管理员', role: 'admin' as const, account: 'admin' },
  },
}

function restoreSession(): SessionUser | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    currentUser: restoreSession() as SessionUser | null,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.currentUser),
    role: (state) => state.currentUser?.role ?? null,
  },
  actions: {
    login(role: UserRole, account: string, password: string) {
      const target = PRESET_ACCOUNTS[role]
      if (account !== target.account || password !== target.password) {
        throw new Error('账号或密码不正确')
      }
      this.currentUser = target.user
      localStorage.setItem(SESSION_KEY, JSON.stringify(target.user))
      return target.user
    },
    logout() {
      this.currentUser = null
      localStorage.removeItem(SESSION_KEY)
    },
  },
})
