<script setup lang="ts">
import { Lock, UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
</script>

<template>
  <div class="page-container settings-page">
    <div class="title-row"><div><h1 class="page-title">系统设置</h1><div class="page-subtitle">查看当前账号与临床辅助系统安全规则。</div></div></div>
    <div class="settings-grid">
      <section class="card profile-card">
        <div class="section-header"><div class="icon"><el-icon><UserFilled /></el-icon></div><div><strong>账号信息</strong><span>当前登录医务人员</span></div></div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="姓名">{{ auth.doctor?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="职称">{{ auth.doctor?.title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="科室">{{ auth.doctor?.department || '-' }}</el-descriptions-item>
          <el-descriptions-item label="用户编号">{{ auth.doctor?.id || '-' }}</el-descriptions-item>
        </el-descriptions>
      </section>
      <section class="card security-card">
        <div class="section-header"><div class="icon lock"><el-icon><Lock /></el-icon></div><div><strong>安全与临床使用规范</strong><span>系统使用边界</span></div></div>
        <div class="rules"><div><i></i><p><strong>访问控制</strong><span>患者数据仅向已授权医务人员开放。</span></p></div><div><i></i><p><strong>来源可追溯</strong><span>知识问答结果应展示对应患者记录和医学资料来源。</span></p></div><div><i></i><p><strong>人工复核</strong><span>系统结果用于辅助分析，最终诊疗决策由临床医生完成。</span></p></div><div><i></i><p><strong>最小必要原则</strong><span>患者信息展示和调用应限定在当前业务需要范围内。</span></p></div></div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-page { padding-top: 24px; }
.title-row { margin-bottom: 18px; }
.settings-grid { display: grid; grid-template-columns: minmax(420px,.8fr) minmax(520px,1.2fr); gap: 15px; align-items: start; }
.profile-card, .security-card { padding: 18px; }
.section-header { display: flex; gap: 11px; align-items: center; margin-bottom: 17px; }
.section-header .icon { width: 39px; height: 39px; border-radius: 10px; background: #e8f6f3; color: #0f766e; display: grid; place-items: center; }
.section-header .icon.lock { background: #edf4fa; color: #3b7099; }
.section-header > div:last-child { display: flex; flex-direction: column; gap: 3px; }
.section-header strong { color: #29465b; font-size: 13px; }
.section-header span { color: #909eac; font-size: 10px; }
.rules { display: flex; flex-direction: column; gap: 11px; }
.rules > div { display: flex; gap: 11px; border: 1px solid #e8edf2; border-radius: 9px; padding: 12px; background: #fbfcfd; }
.rules i { width: 7px; height: 7px; border-radius: 50%; background: #37a087; margin-top: 5px; flex: 0 0 7px; }
.rules p { margin: 0; display: flex; flex-direction: column; gap: 4px; }
.rules strong { color: #3a5367; font-size: 11px; }
.rules span { color: #748698; font-size: 10px; line-height: 1.55; }
</style>
