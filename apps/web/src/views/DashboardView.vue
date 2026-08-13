<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ChatDotRound, Collection, DataAnalysis, UserFilled, WarningFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { usePatientsStore } from '@/stores/patients'

const router = useRouter()
const store = usePatientsStore()

onMounted(() => store.loadPatients())

const highRiskCount = computed(() => store.patients.filter((item) => item.riskLevel === '高').length)
const mediumRiskCount = computed(() => store.patients.filter((item) => item.riskLevel === '中').length)
const stableCount = computed(() => store.patients.filter((item) => item.status === '稳定').length)
const recentPatients = computed(() => [...store.patients].sort((a, b) => b.lastVisit.localeCompare(a.lastVisit)).slice(0, 5))
</script>

<template>
  <div class="page-container dashboard-page">
    <div class="page-heading">
      <div>
        <h1 class="page-title">系统首页</h1>
        <p class="page-subtitle">统一查看患者管理、医学知识库与临床辅助问答运行概况。</p>
      </div>
    </div>

    <div class="stat-grid">
      <section class="stat-card card">
        <div class="stat-icon teal"><el-icon><UserFilled /></el-icon></div>
        <div><span>患者总数</span><strong>{{ store.patients.length }}</strong><em>当前管理患者</em></div>
      </section>
      <section class="stat-card card">
        <div class="stat-icon red"><el-icon><WarningFilled /></el-icon></div>
        <div><span>重点关注</span><strong>{{ highRiskCount }}</strong><em>高风险患者</em></div>
      </section>
      <section class="stat-card card">
        <div class="stat-icon blue"><el-icon><Collection /></el-icon></div>
        <div><span>医学知识文档</span><strong>0</strong><em>已纳入知识库</em></div>
      </section>
      <section class="stat-card card">
        <div class="stat-icon amber"><el-icon><ChatDotRound /></el-icon></div>
        <div><span>今日知识问答</span><strong>0</strong><em>临床知识检索</em></div>
      </section>
    </div>

    <div class="dashboard-grid">
      <section class="card recent-card">
        <div class="section-header">
          <div>
            <strong>近期患者</strong>
            <span>按最近就诊时间排列</span>
          </div>
          <el-button type="primary" link @click="router.push('/patients')">查看全部患者</el-button>
        </div>
        <el-table v-loading="store.loading" :data="recentPatients" size="large">
          <el-table-column prop="name" label="姓名" width="90" />
          <el-table-column label="主要诊断" min-width="230">
            <template #default="{ row }">
              <div class="tag-row"><el-tag v-for="item in row.diagnoses" :key="item" size="small" effect="plain">{{ item }}</el-tag></div>
            </template>
          </el-table-column>
          <el-table-column prop="lastVisit" label="最近就诊" width="120" />
          <el-table-column label="风险等级" width="100">
            <template #default="{ row }">
              <el-tag :type="row.riskLevel === '高' ? 'danger' : row.riskLevel === '中' ? 'warning' : 'success'" size="small">{{ row.riskLevel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="95" align="right">
            <template #default="{ row }"><el-button type="primary" link @click="router.push(`/patients/${row.id}`)">查看详情</el-button></template>
          </el-table-column>
        </el-table>
      </section>

      <div class="side-stack">
        <section class="card risk-card">
          <div class="section-header compact">
            <div><strong>患者风险分布</strong><span>当前患者分层情况</span></div>
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="risk-list">
            <div class="risk-row"><span><i class="dot high"></i>高风险</span><strong>{{ highRiskCount }}</strong></div>
            <div class="bar"><i class="high" :style="{ width: `${store.patients.length ? highRiskCount / store.patients.length * 100 : 0}%` }"></i></div>
            <div class="risk-row"><span><i class="dot medium"></i>中风险</span><strong>{{ mediumRiskCount }}</strong></div>
            <div class="bar"><i class="medium" :style="{ width: `${store.patients.length ? mediumRiskCount / store.patients.length * 100 : 0}%` }"></i></div>
            <div class="risk-row"><span><i class="dot low"></i>稳定患者</span><strong>{{ stableCount }}</strong></div>
            <div class="bar"><i class="low" :style="{ width: `${store.patients.length ? stableCount / store.patients.length * 100 : 0}%` }"></i></div>
          </div>
        </section>

        <section class="card quick-card">
          <div class="section-header compact"><div><strong>快捷入口</strong><span>常用业务功能</span></div></div>
          <button @click="router.push('/patients')"><el-icon><UserFilled /></el-icon><div><strong>患者管理</strong><span>查看患者档案与历史记录</span></div></button>
          <button @click="router.push('/knowledge')"><el-icon><Collection /></el-icon><div><strong>知识库管理</strong><span>管理医学指南与专业资料</span></div></button>
          <button @click="router.push('/knowledge-chat')"><el-icon><ChatDotRound /></el-icon><div><strong>医学知识问答</strong><span>检索医学知识并查看依据</span></div></button>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-page { padding-top: 24px; }
.page-heading { display: flex; justify-content: space-between; align-items: end; margin-bottom: 20px; }
.stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-bottom: 16px; }
.stat-card { padding: 18px; display: flex; align-items: center; gap: 14px; min-height: 100px; }
.stat-icon { width: 48px; height: 48px; border-radius: 13px; display: grid; place-items: center; font-size: 22px; }
.stat-icon.teal { color: #0f766e; background: #e7f6f3; }
.stat-icon.red { color: #b74f4a; background: #fbeceb; }
.stat-icon.blue { color: #3a6f98; background: #edf4fa; }
.stat-icon.amber { color: #a86d22; background: #fcf4e8; }
.stat-card > div:last-child { display: flex; flex-direction: column; }
.stat-card span { color: #7e8d9d; font-size: 11px; }
.stat-card strong { color: #17394f; font-size: 26px; margin: 2px 0; line-height: 1.2; }
.stat-card em { color: #9ba6b2; font-style: normal; font-size: 10px; }
.dashboard-grid { display: grid; grid-template-columns: minmax(650px, 1.5fr) minmax(330px, .7fr); gap: 16px; align-items: start; }
.recent-card { overflow: hidden; }
.section-header { min-height: 69px; padding: 0 18px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e8edf2; }
.section-header.compact { min-height: 62px; }
.section-header > div { display: flex; flex-direction: column; gap: 4px; }
.section-header strong { color: #29465b; font-size: 14px; }
.section-header span { color: #93a0ad; font-size: 10px; }
.section-header > .el-icon { color: #6a8799; font-size: 19px; }
.tag-row { display: flex; gap: 5px; flex-wrap: wrap; }
.side-stack { display: flex; flex-direction: column; gap: 16px; }
.risk-list { padding: 16px 18px 20px; }
.risk-row { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; color: #52697c; font-size: 12px; }
.risk-row:first-child { margin-top: 0; }
.risk-row span { display: flex; align-items: center; gap: 7px; }
.risk-row strong { color: #29465b; }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.dot.high, .bar i.high { background: #c65f57; }
.dot.medium, .bar i.medium { background: #d69b43; }
.dot.low, .bar i.low { background: #4ba381; }
.bar { height: 6px; background: #edf1f4; border-radius: 999px; overflow: hidden; margin: 7px 0 13px; }
.bar i { display: block; height: 100%; border-radius: inherit; }
.quick-card { overflow: hidden; }
.quick-card button { width: 100%; border: 0; border-bottom: 1px solid #edf1f4; background: #fff; padding: 14px 18px; display: flex; align-items: center; gap: 12px; text-align: left; cursor: pointer; transition: .2s; }
.quick-card button:last-child { border-bottom: 0; }
.quick-card button:hover { background: #f5faf9; }
.quick-card button > .el-icon { width: 34px; height: 34px; border-radius: 9px; background: #eaf6f4; color: #0f766e; font-size: 17px; }
.quick-card button div { display: flex; flex-direction: column; gap: 3px; }
.quick-card button strong { color: #304b60; font-size: 12px; }
.quick-card button span { color: #8b98a6; font-size: 10px; }
</style>
