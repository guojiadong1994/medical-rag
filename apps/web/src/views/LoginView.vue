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
const form = reactive({ username: 'doctor', password: '123456' })
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
    router.replace('/patients')
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
      <div class="visual-overlay">
        <div class="brand-mark">JD</div>
        <p class="eyebrow">医疗知识增强检索子系统</p>
        <h1>让长期患者信息与<br />权威医学知识真正连接</h1>
        <p class="lead">统一查看患者事实，检索医学指南与专业资料，为临床医生提供有依据、可追溯的辅助分析。</p>
        <div class="feature-row">
          <span>患者纵向档案</span><i></i><span>医学知识库</span><i></i><span>检索增强问答</span>
        </div>
      </div>
    </div>

    <div class="form-panel">
      <div class="login-card">
        <div class="login-heading">
          <span>医生工作台</span>
          <h2>账号登录</h2>
          <p>请输入医生账号进入系统</p>
        </div>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" :prefix-icon="User" placeholder="账号" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" :prefix-icon="Lock" type="password" show-password placeholder="密码" />
          </el-form-item>
          <el-button class="login-btn" type="primary" size="large" :loading="loading" @click="submit">登录系统</el-button>
        </el-form>

        <div class="demo-account">
          <strong>第一版演示账号</strong>
          <span>账号：doctor　密码：123456</span>
        </div>
        <p class="security-note">当前使用模拟登录，下一阶段接入 FastAPI 身份认证与权限控制。</p>
      </div>
      <div class="copyright">JD 特定人群生理孪生与医疗保障大模型平台 · V0.1</div>
    </div>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(540px, 1.16fr) minmax(520px, .84fr); background: white; }
.visual-panel { min-height: 100vh; background: radial-gradient(circle at 20% 22%, rgba(81,192,171,.25), transparent 32%), radial-gradient(circle at 78% 70%, rgba(54,122,155,.25), transparent 28%), linear-gradient(135deg, #0b3f4d 0%, #0d5f63 48%, #163e57 100%); color: white; overflow: hidden; position: relative; }
.visual-panel::after { content: ''; position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px); background-size: 38px 38px; }
.visual-overlay { position: relative; z-index: 2; width: 72%; margin: 0 auto; padding-top: 19vh; }
.brand-mark { width: 54px; height: 54px; display: grid; place-items: center; border-radius: 15px; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.26); font-weight: 800; letter-spacing: 1px; backdrop-filter: blur(8px); }
.eyebrow { margin: 28px 0 10px; color: #bce7df; letter-spacing: 2px; font-size: 12px; }
h1 { margin: 0; font-size: 40px; line-height: 1.35; letter-spacing: .5px; font-weight: 720; }
.lead { margin: 24px 0 0; max-width: 620px; color: #d4e7e8; line-height: 1.9; font-size: 15px; }
.feature-row { margin-top: 42px; display: flex; align-items: center; gap: 13px; font-size: 12px; color: #cde5e6; }
.feature-row i { width: 4px; height: 4px; background: #73c8b8; border-radius: 50%; }
.form-panel { display: flex; align-items: center; justify-content: center; position: relative; background: #fbfcfe; }
.login-card { width: 390px; }
.login-heading span { color: #0f766e; font-size: 13px; font-weight: 700; }
.login-heading h2 { color: #17344b; font-size: 29px; margin: 10px 0 8px; }
.login-heading p { color: #7b8b9d; margin: 0 0 31px; font-size: 14px; }
.login-btn { width: 100%; margin-top: 4px; font-weight: 650; letter-spacing: 2px; }
.demo-account { margin-top: 25px; padding: 12px 14px; border-radius: 10px; background: #f0f8f6; border: 1px dashed #b8dcd6; display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #52706d; }
.demo-account strong { color: #236b63; }
.security-note { margin-top: 13px; color: #95a0ad; font-size: 11px; line-height: 1.6; text-align: center; }
.copyright { position: absolute; bottom: 26px; color: #a1acb9; font-size: 11px; }
</style>
