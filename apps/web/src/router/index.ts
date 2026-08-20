import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import AppLayout from '@/layouts/AppLayout.vue'
import UserHomeView from '@/views/UserHomeView.vue'
import UserHealthView from '@/views/UserHealthView.vue'
import UserRecordsView from '@/views/UserRecordsView.vue'
import UserAssistantView from '@/views/UserAssistantView.vue'
import UserSettingsView from '@/views/UserSettingsView.vue'
import AdminKnowledgeView from '@/views/AdminKnowledgeView.vue'
function getSession() { try { const raw = localStorage.getItem('medical-rag-session'); return raw ? JSON.parse(raw) as { role: 'user'|'admin' } : null } catch { return null } }
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: LoginView },
  { path: '/user', component: AppLayout, meta: { requiresAuth: true, role: 'user' }, children: [
    { path: '', redirect: '/user/home' }, { path: 'home', component: UserHomeView, meta: { title: '首页' } },
    { path: 'health', component: UserHealthView, meta: { title: '我的健康' } }, { path: 'records', component: UserRecordsView, meta: { title: '医疗记录' } },
    { path: 'assistant', component: UserAssistantView, meta: { title: 'AI 健康助手' } }, { path: 'settings', component: UserSettingsView, meta: { title: '设置' } },
  ] },
  { path: '/admin', component: AppLayout, meta: { requiresAuth: true, role: 'admin' }, children: [
    { path: '', redirect: '/admin/knowledge' }, { path: 'knowledge', component: AdminKnowledgeView, meta: { title: '医疗知识库管理' } },
  ] },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
] })
router.beforeEach((to) => {
  const session = getSession(); if (to.path === '/login' && session) return session.role === 'admin' ? '/admin/knowledge' : '/user/home'
  if (to.meta.requiresAuth && !session) return '/login'
  const requiredRole = to.matched.find((record) => record.meta.role)?.meta.role
  if (requiredRole && session?.role !== requiredRole) return session?.role === 'admin' ? '/admin/knowledge' : '/user/home'
  return true
})
export default router
