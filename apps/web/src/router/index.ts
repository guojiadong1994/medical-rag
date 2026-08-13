import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import DashboardView from '@/views/DashboardView.vue'
import PatientListView from '@/views/PatientListView.vue'
import PatientDetailView from '@/views/PatientDetailView.vue'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'
import KnowledgeChatView from '@/views/KnowledgeChatView.vue'
import SystemSettingsView from '@/views/SystemSettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true, title: '登录' } },
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: DashboardView, meta: { title: '系统首页' } },
        { path: 'patients', name: 'patients', component: PatientListView, meta: { title: '患者列表' } },
        { path: 'patients/:patientId', name: 'patient-detail', component: PatientDetailView, meta: { title: '患者详情' } },
        { path: 'knowledge', name: 'knowledge', component: KnowledgeBaseView, meta: { title: '知识库管理' } },
        { path: 'knowledge-chat', name: 'knowledge-chat', component: KnowledgeChatView, meta: { title: '医学知识问答' } },
        { path: 'settings', name: 'settings', component: SystemSettingsView, meta: { title: '系统设置' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('medical-rag-token')
  if (!to.meta.public && !token) return { name: 'login' }
  if (to.name === 'login' && token) return { name: 'dashboard' }
  return true
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title ?? '医疗保障大模型平台')} - 医疗保障大模型平台`
})

export default router
