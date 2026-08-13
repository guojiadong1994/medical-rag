<script setup lang="ts">
import { ArrowDown, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function handleCommand(command: string) {
  if (command === 'logout') {
    auth.logout()
    router.replace('/login')
  }
}
</script>

<template>
  <div class="page-shell">
    <header class="topbar">
      <div class="brand" @click="router.push('/patients')">
        <div class="brand-mark">JD</div>
        <div>
          <div class="brand-title">医疗保障大模型平台</div>
          <div class="brand-subtitle">多源医疗知识增强检索子系统</div>
        </div>
      </div>

      <div class="topbar-right">
        <span class="demo-badge">演示环境</span>
        <el-dropdown @command="handleCommand">
          <div class="doctor-entry">
            <el-avatar :size="34" :icon="UserFilled" />
            <div class="doctor-copy">
              <strong>{{ auth.doctor?.name || '医生用户' }}</strong>
              <span>{{ auth.doctor?.department || '医疗中心' }}</span>
            </div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item disabled>个人设置</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>
    <main><slot /></main>
  </div>
</template>

<style scoped>
.topbar { height: 68px; background: #fff; border-bottom: 1px solid #e7edf3; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; position: sticky; top: 0; z-index: 20; box-shadow: 0 2px 12px rgba(42, 67, 91, .035); }
.brand { display: flex; align-items: center; gap: 12px; cursor: pointer; }
.brand-mark { width: 38px; height: 38px; border-radius: 11px; background: linear-gradient(145deg, #0f766e, #0b5f73); color: white; display: grid; place-items: center; font-weight: 800; font-size: 15px; letter-spacing: .6px; box-shadow: 0 7px 18px rgba(15,118,110,.18); }
.brand-title { font-size: 16px; font-weight: 750; color: #163047; }
.brand-subtitle { font-size: 11px; color: #7b8da1; margin-top: 2px; }
.topbar-right { display: flex; align-items: center; gap: 18px; }
.demo-badge { font-size: 12px; color: #7c6a32; border: 1px solid #eadfae; background: #fffbed; padding: 5px 9px; border-radius: 999px; }
.doctor-entry { display: flex; align-items: center; gap: 9px; cursor: pointer; outline: none; }
.doctor-copy { display: flex; flex-direction: column; min-width: 116px; }
.doctor-copy strong { font-size: 13px; color: #24384b; }
.doctor-copy span { color: #8291a2; font-size: 11px; margin-top: 2px; }
</style>
