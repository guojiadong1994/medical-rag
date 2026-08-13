<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  await formRef.value?.validate()
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.replace('/dashboard')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="visual-panel">
      <div class="visual-content">
        <div class="brand-mark">JD</div>
        <p class="eyebrow">医疗保障智能辅助平台</p>
        <h1>连接患者长期健康信息<br />与权威医学知识</h1>
        <p class="lead">面向临床医生统一呈现患者纵向记录，并通过医学知识增强检索提供可追溯的辅助分析依据。</p>
        <div class="feature-row">
          <span>患者纵向档案</span><i></i><span>医学知识检索</span><i></i><span>临床辅助问答</span>
        </div>
      </div>
    </div>

    <div class="form-panel">
      <div class="login-card">
        <div class="login-heading">
          <span>医生工作台</span>
          <h2>账号登录</h2>
          <p>请输入工作账号和密码进入系统</p>
        </div>
        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" :prefix-icon="User" autocomplete="username" placeholder="账号" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" :prefix-icon="Lock" type="password" show-password autocomplete="current-password" placeholder="密码" />
          </el-form-item>
          <el-button class="login-btn" type="primary" size="large" :loading="loading" @click="submit">登录系统</el-button>
        </el-form>
        <div class="security-note">仅限授权医务人员使用，系统访问和操作行为将进行安全审计。</div>
      </div>
      <div class="copyright">JD 特定人群生理孪生与医疗保障大模型平台</div>
    </div>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(560px, 1.1fr) minmax(500px, .9fr); background: #fff; }
.visual-panel { min-height: 100vh; position: relative; overflow: hidden; color: #fff; background: radial-gradient(circle at 18% 18%, rgba(63,196,176,.28), transparent 30%), radial-gradient(circle at 76% 76%, rgba(65,123,166,.28), transparent 28%), linear-gradient(135deg, #0a3644 0%, #0c5a61 48%, #173d57 100%); }
.visual-panel::after { content: ''; position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.022) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.022) 1px, transparent 1px); background-size: 40px 40px; }
.visual-content { width: 72%; margin: 0 auto; padding-top: 18vh; position: relative; z-index: 2; }
.brand-mark { width: 56px; height: 56px; border-radius: 16px; display: grid; place-items: center; background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.24); font-weight: 800; letter-spacing: 1px; backdrop-filter: blur(8px); }
.eyebrow { margin: 29px 0 11px; color: #b9e7df; letter-spacing: 2px; font-size: 12px; }
h1 { margin: 0; font-size: 40px; line-height: 1.4; font-weight: 720; letter-spacing: .4px; }
.lead { max-width: 620px; margin: 23px 0 0; color: #d4e6e8; line-height: 1.9; font-size: 15px; }
.feature-row { margin-top: 42px; display: flex; align-items: center; gap: 13px; color: #cce4e6; font-size: 12px; }
.feature-row i { width: 4px; height: 4px; border-radius: 50%; background: #73c9ba; }
.form-panel { display: flex; justify-content: center; align-items: center; position: relative; background: #fbfcfe; }
.login-card { width: 390px; }
.login-heading span { color: #0f766e; font-size: 13px; font-weight: 700; }
.login-heading h2 { margin: 10px 0 8px; color: #17354b; font-size: 29px; }
.login-heading p { margin: 0 0 31px; color: #7c8c9e; font-size: 14px; }
.login-btn { width: 100%; margin-top: 4px; font-weight: 650; letter-spacing: 2px; }
.security-note { margin-top: 19px; padding-top: 17px; border-top: 1px solid #edf1f4; text-align: center; color: #98a4b0; font-size: 11px; line-height: 1.7; }
.copyright { position: absolute; bottom: 26px; color: #a2adba; font-size: 11px; }
</style>
