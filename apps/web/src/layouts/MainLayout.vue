<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  ChatDotRound,
  Collection,
  HomeFilled,
  Setting,
  UserFilled,
  User,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => {
  if (route.path.startsWith('/patients')) return '/patients'
  if (route.path.startsWith('/knowledge-chat')) return '/knowledge-chat'
  if (route.path.startsWith('/knowledge')) return '/knowledge'
  if (route.path.startsWith('/settings')) return '/settings'
  return '/dashboard'
})

const pageTitle = computed(() => String(route.meta.title ?? '系统首页'))

function navigate(path: string) {
  router.push(path)
}

function handleCommand(command: string) {
  if (command === 'logout') {
    auth.logout()
    router.replace('/login')
  }
  if (command === 'settings') {
    router.push('/settings')
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand" @click="navigate('/dashboard')">
        <div class="brand-mark">JD</div>
        <div class="brand-copy">
          <strong>医疗保障大模型平台</strong>
          <span>医疗知识增强检索子系统</span>
        </div>
      </div>

      <el-menu class="side-menu" :default-active="activeMenu" @select="navigate">
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>系统首页</span>
        </el-menu-item>
        <el-menu-item index="/patients">
          <el-icon><User /></el-icon>
          <span>患者管理</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>
        <el-menu-item index="/knowledge-chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>医学知识问答</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <div class="security-dot"></div>
        <div>
          <strong>临床辅助系统</strong>
          <span>所有回答需由医生复核</span>
        </div>
      </div>
    </aside>

    <section class="main-area">
      <header class="topbar">
        <div class="header-title">
          <span>医疗保障智能辅助工作台</span>
          <strong>{{ pageTitle }}</strong>
        </div>
        <div class="header-actions">
          <el-dropdown @command="handleCommand">
            <div class="doctor-entry">
              <el-avatar :size="36" :icon="UserFilled" />
              <div class="doctor-copy">
                <strong>{{ auth.doctor?.name || '医生用户' }}</strong>
                <span>{{ auth.doctor?.department || '医疗中心' }}</span>
              </div>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="settings">个人设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content-area">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; display: flex; background: #f3f6fa; }
.sidebar { width: 238px; min-height: 100vh; background: #102e3b; color: #fff; display: flex; flex-direction: column; position: fixed; inset: 0 auto 0 0; z-index: 40; box-shadow: 8px 0 28px rgba(11, 35, 49, .08); }
.brand { height: 82px; display: flex; align-items: center; gap: 11px; padding: 0 18px; border-bottom: 1px solid rgba(255,255,255,.08); cursor: pointer; }
.brand-mark { width: 39px; height: 39px; border-radius: 11px; display: grid; place-items: center; background: linear-gradient(145deg, #26a69a, #197a88); font-weight: 800; letter-spacing: .8px; box-shadow: 0 8px 20px rgba(0,0,0,.14); }
.brand-copy { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.brand-copy strong { font-size: 14px; white-space: nowrap; }
.brand-copy span { font-size: 10px; color: #9bb7c3; white-space: nowrap; }
.side-menu { border-right: 0; background: transparent; padding: 14px 10px; --el-menu-bg-color: transparent; --el-menu-text-color: #bdd0d8; --el-menu-hover-bg-color: rgba(255,255,255,.065); --el-menu-active-color: #fff; }
.side-menu :deep(.el-menu-item) { height: 48px; border-radius: 9px; margin-bottom: 5px; }
.side-menu :deep(.el-menu-item.is-active) { background: linear-gradient(90deg, rgba(40,166,154,.3), rgba(40,166,154,.12)); color: #fff; position: relative; }
.side-menu :deep(.el-menu-item.is-active)::before { content: ''; position: absolute; left: 0; width: 3px; height: 24px; border-radius: 0 3px 3px 0; background: #47c3b7; }
.side-menu :deep(.el-icon) { font-size: 18px; }
.sidebar-footer { margin: auto 14px 17px; padding: 13px 12px; border: 1px solid rgba(255,255,255,.08); border-radius: 10px; display: flex; align-items: center; gap: 9px; background: rgba(255,255,255,.035); }
.security-dot { width: 8px; height: 8px; border-radius: 50%; background: #52c795; box-shadow: 0 0 0 4px rgba(82,199,149,.12); }
.sidebar-footer div:last-child { display: flex; flex-direction: column; gap: 3px; }
.sidebar-footer strong { font-size: 11px; color: #d6e3e8; }
.sidebar-footer span { font-size: 9px; color: #8eaab6; }
.main-area { width: calc(100% - 238px); min-height: 100vh; margin-left: 238px; }
.topbar { height: 68px; background: #fff; border-bottom: 1px solid #e5ebf0; display: flex; align-items: center; justify-content: space-between; padding: 0 26px; position: sticky; top: 0; z-index: 30; box-shadow: 0 2px 12px rgba(42, 67, 91, .025); }
.header-title { display: flex; align-items: baseline; gap: 12px; }
.header-title span { color: #8898a8; font-size: 11px; }
.header-title strong { color: #17384e; font-size: 18px; }
.header-actions { display: flex; align-items: center; }
.doctor-entry { display: flex; align-items: center; gap: 9px; cursor: pointer; outline: none; }
.doctor-copy { display: flex; flex-direction: column; min-width: 114px; }
.doctor-copy strong { color: #29465b; font-size: 13px; }
.doctor-copy span { color: #8898a8; font-size: 10px; margin-top: 2px; }
.content-area { min-height: calc(100vh - 68px); }
</style>
