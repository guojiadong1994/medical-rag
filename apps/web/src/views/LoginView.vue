<template>
  <div class="login-page">
    <section class="login-hero">
      <div class="login-brand">
        <div class="brand-mark">智</div>
        <div>
          <div class="brand-title">智护医疗</div>
          <div class="brand-subtitle">个人健康智能服务平台</div>
        </div>
      </div>

      <div class="login-copy">
        <h1>让每一份医疗数据，<br />真正服务于你的健康。</h1>
        <p>连接授权医疗机构，汇聚个人诊疗记录、检验检查与用药信息，并结合权威医学知识，为你提供连续、可追溯的健康信息解读服务。</p>
        <div class="login-points">
          <div class="login-point"><span class="point-dot">✓</span> 医疗机构数据统一汇聚</div>
          <div class="login-point"><span class="point-dot">✓</span> 个人健康信息持续更新</div>
          <div class="login-point"><span class="point-dot">✓</span> AI 回答提供医疗记录与医学依据</div>
        </div>
      </div>
    </section>

    <section class="login-side">
      <div class="login-card">
        <h2>欢迎登录</h2>
        <p>请选择登录身份并进入对应服务空间</p>

        <div class="role-switch">
          <button class="role-button" :class="{ active: role === 'user' }" @click="switchRole('user')">个人登录</button>
          <button class="role-button" :class="{ active: role === 'admin' }" @click="switchRole('admin')">管理员登录</button>
        </div>

        <div class="credential-tip">
          当前账号信息已预置，可直接登录。<br />
          {{ role === 'user' ? '个人账号用于访问本人健康档案与医疗记录。' : '管理员账号用于维护平台医疗知识库。' }}
        </div>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="账号">
            <el-input v-model="account" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" size="large" type="password" show-password autocomplete="current-password" @keyup.enter="submit" />
          </el-form-item>
          <el-button class="login-submit" type="primary" size="large" :loading="loading" @click="submit">
            {{ role === 'user' ? '进入个人健康中心' : '进入管理控制台' }}
          </el-button>
        </el-form>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PRESET_ACCOUNTS, useAuthStore, type UserRole } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const role = ref<UserRole>('user')
const account = ref(PRESET_ACCOUNTS.user.account)
const password = ref(PRESET_ACCOUNTS.user.password)
const loading = ref(false)

function switchRole(next: UserRole) {
  role.value = next
  account.value = PRESET_ACCOUNTS[next].account
  password.value = PRESET_ACCOUNTS[next].password
}

async function submit() {
  loading.value = true
  try {
    const user = auth.login(role.value, account.value.trim(), password.value)
    await router.replace(user.role === 'admin' ? '/admin/knowledge' : '/user/home')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
