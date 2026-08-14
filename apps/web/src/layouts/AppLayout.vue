<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">智</div>
        <div>
          <div class="brand-title">智护医疗</div>
          <div class="brand-subtitle">健康智能服务平台</div>
        </div>
      </div>

      <nav class="nav-list" v-if="auth.role === 'user'">
        <RouterLink v-for="item in userNav" :key="item.path" :to="item.path" class="nav-item">
          <component :is="item.icon" class="nav-icon" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <nav class="nav-list" v-else>
        <RouterLink to="/admin/knowledge" class="nav-item">
          <Collection class="nav-icon" />
          <span>医疗知识库</span>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="account-card">
          <el-avatar :size="38">{{ auth.currentUser?.name?.slice(0, 1) }}</el-avatar>
          <div class="account-copy">
            <strong>{{ auth.currentUser?.name }}</strong>
            <span>{{ auth.role === 'admin' ? '平台管理员' : '个人用户' }}</span>
          </div>
        </div>
        <el-button class="sidebar-logout" text @click="confirmLogout">
          <SwitchButton />
          <span>退出登录</span>
        </el-button>
      </div>
    </aside>

    <main class="main-area">
      <header class="topbar">
        <div>
          <h1>{{ currentTitle }}</h1>
          <p>{{ currentSubtitle }}</p>
        </div>
        <div class="topbar-right">
          <el-tag v-if="auth.role === 'user'" type="success" effect="plain" round>医疗数据已同步</el-tag>
          <el-tag v-else type="info" effect="plain" round>管理控制台</el-tag>

          <el-dropdown trigger="click" @command="handleAccountCommand">
            <button class="top-account-button" type="button">
              <el-avatar :size="34">{{ auth.currentUser?.name?.slice(0, 1) }}</el-avatar>
              <div class="top-account-copy">
                <strong>{{ auth.currentUser?.name }}</strong>
                <span>{{ auth.role === 'admin' ? '管理员' : '个人用户' }}</span>
              </div>
              <ArrowDown class="top-account-arrow" />
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  当前账号：{{ auth.currentUser?.account }}
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <SwitchButton />
                  <span style="margin-left:8px">退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <section class="page-body">
        <router-view />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { House, User, Document, MagicStick, Setting, Collection, SwitchButton, ArrowDown } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const userNav = [
  { path: '/user/home', label: '首页', icon: House },
  { path: '/user/health', label: '我的健康', icon: User },
  { path: '/user/records', label: '医疗记录', icon: Document },
  { path: '/user/assistant', label: 'AI 健康助手', icon: MagicStick },
  { path: '/user/settings', label: '设置', icon: Setting },
]

const currentTitle = computed(() => String(route.meta.title ?? '智护医疗'))
const currentSubtitle = computed(() => {
  const title = currentTitle.value
  const map: Record<string, string> = {
    '首页': '了解近期健康状态与重要变化',
    '我的健康': '汇总个人健康档案、用药与关键指标',
    '医疗记录': '查看来自已关联医疗机构的诊疗记录',
    'AI 健康助手': '基于个人医疗记录与权威医学知识提供辅助解读',
    '设置': '管理账号、数据授权与医疗机构关联',
    '医疗知识库管理': '维护平台医学知识来源与检索索引',
  }
  return map[title] ?? ''
})

async function confirmLogout() {
  try {
    await ElMessageBox.confirm(
      '退出后需要重新登录才能继续访问当前系统。',
      '确认退出登录？',
      {
        confirmButtonText: '退出登录',
        cancelButtonText: '取消',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }

  auth.logout()
  sessionStorage.removeItem('assistant-prefill')
  await router.replace('/login')
  ElMessage.success('已安全退出登录')
}

function handleAccountCommand(command: string) {
  if (command === 'logout') {
    void confirmLogout()
  }
}
</script>
