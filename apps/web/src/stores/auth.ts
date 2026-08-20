import { defineStore } from 'pinia'
import { clearAccessToken, setAccessToken } from '@/api/client'

export type UserRole = 'user' | 'admin'
export interface SessionUser { id: string; name: string; role: UserRole; account: string }
const SESSION_KEY = 'medical-rag-session'
export const PRESET_ACCOUNTS = {
  user: { account: 'user001', password: '123456' },
  admin: { account: 'admin', password: 'admin123' },
}
function restoreSession(): SessionUser | null {
  try { const raw = localStorage.getItem(SESSION_KEY); return raw ? JSON.parse(raw) : null } catch { return null }
}
export const useAuthStore = defineStore('auth', {
  state: () => ({ currentUser: restoreSession() as SessionUser | null }),
  getters: { isAuthenticated: (state) => Boolean(state.currentUser), role: (state) => state.currentUser?.role ?? null },
  actions: {
    async login(role: UserRole, account: string, password: string) {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: account, password }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.detail || '账号或密码不正确')
      const user: SessionUser = payload.user ?? { id: role === 'admin' ? 'A10001' : 'U10001', name: role === 'admin' ? '系统管理员' : '郭嘉栋', role, account }
      if (user.role !== role) throw new Error('账号身份与当前登录入口不一致')
      this.currentUser = user
      localStorage.setItem(SESSION_KEY, JSON.stringify(user))
      setAccessToken(payload.accessToken)
      return user
    },
    logout() { this.currentUser = null; localStorage.removeItem(SESSION_KEY); clearAccessToken() },
  },
})
