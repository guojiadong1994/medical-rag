import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '@/views/LoginView.vue'
import PatientListView from '@/views/PatientListView.vue'
import PatientDetailView from '@/views/PatientDetailView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/patients' },
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/patients', name: 'patients', component: PatientListView },
    { path: '/patients/:patientId', name: 'patient-detail', component: PatientDetailView },
    { path: '/:pathMatch(.*)*', redirect: '/patients' },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('medical-rag-token')
  if (!to.meta.public && !token) return { name: 'login' }
  if (to.name === 'login' && token) return { name: 'patients' }
  return true
})

export default router
