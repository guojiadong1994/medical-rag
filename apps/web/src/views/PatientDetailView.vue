<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { ArrowLeft, Calendar, DocumentChecked, FirstAidKit, Warning } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import RagChatPanel from '@/components/RagChatPanel.vue'
import { usePatientsStore } from '@/stores/patients'

const route = useRoute()
const router = useRouter()
const store = usePatientsStore()
const patientId = computed(() => String(route.params.patientId))

async function load() {
  await store.loadPatientDetail(patientId.value)
}

onMounted(load)
watch(patientId, load)

const reportEvents = computed(() => store.activePatient?.timeline.filter((item) => item.type === '检查' || item.type === '检验') ?? [])

function metricClass(status: string) {
  return status === '正常' ? 'normal' : 'warning'
}
</script>

<template>
  <div v-loading="store.loading" class="page-container detail-page">
    <template v-if="store.activePatient">
      <div class="detail-topline">
        <el-button text :icon="ArrowLeft" @click="router.push('/patients')">返回患者列表</el-button>
        <span>患者管理 / 患者详情</span>
      </div>

      <section class="card patient-banner">
        <div class="profile-main">
          <div class="patient-avatar">{{ store.activePatient.name.slice(0, 1) }}</div>
          <div>
            <div class="patient-name-row">
              <h2>{{ store.activePatient.name }}</h2>
              <el-tag :type="store.activePatient.riskLevel === '高' ? 'danger' : store.activePatient.riskLevel === '中' ? 'warning' : 'success'" effect="light">{{ store.activePatient.riskLevel }}风险</el-tag>
              <el-tag effect="plain">{{ store.activePatient.status }}</el-tag>
            </div>
            <p>{{ store.activePatient.gender }} · {{ store.activePatient.age }}岁 · 患者编号 {{ store.activePatient.patientNo }}</p>
          </div>
        </div>
        <div class="profile-meta">
          <div><span>最近就诊</span><strong>{{ store.activePatient.lastVisit }}</strong></div>
          <div><span>联系方式</span><strong>{{ store.activePatient.phoneMasked }}</strong></div>
          <div><span>过敏史</span><strong>{{ store.activePatient.allergies.join('、') || '未记录' }}</strong></div>
        </div>
      </section>

      <div class="detail-grid">
        <div class="patient-column">
          <section class="summary-strip">
            <div class="summary-card card"><el-icon><Warning /></el-icon><div><span>主要诊断</span><strong>{{ store.activePatient.diagnoses.join('、') }}</strong></div></div>
            <div class="summary-card card"><el-icon><FirstAidKit /></el-icon><div><span>当前用药</span><strong>{{ store.activePatient.currentMedications.length }} 种</strong></div></div>
            <div class="summary-card card"><el-icon><Calendar /></el-icon><div><span>历史记录</span><strong>{{ store.activePatient.timeline.length }} 条</strong></div></div>
          </section>

          <section class="card patient-info-card">
            <el-tabs>
              <el-tab-pane label="患者概览">
                <div class="overview-block">
                  <div class="section-title">健康状态摘要</div>
                  <p class="care-summary">{{ store.activePatient.careSummary }}</p>
                </div>
                <div class="overview-block">
                  <div class="section-title">近期关键指标</div>
                  <div class="metric-grid">
                    <div v-for="item in store.activePatient.recentMetrics" :key="`${item.name}-${item.date}`" class="metric-item">
                      <span>{{ item.name }}</span>
                      <strong :class="metricClass(item.status)">{{ item.value }} <small>{{ item.unit }}</small></strong>
                      <em>{{ item.date }} · {{ item.status }}</em>
                    </div>
                  </div>
                </div>
                <div class="overview-block">
                  <div class="section-title">慢病情况</div>
                  <div class="tag-row"><el-tag v-for="item in store.activePatient.chronicDiseases" :key="item" effect="plain">{{ item }}</el-tag></div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="历次就诊">
                <el-timeline class="timeline">
                  <el-timeline-item v-for="item in store.activePatient.timeline" :key="item.id" :timestamp="item.date" placement="top">
                    <div class="timeline-item">
                      <div><strong>{{ item.title }}</strong><el-tag size="small" effect="plain">{{ item.type }}</el-tag></div>
                      <p>{{ item.summary }}</p><span>来源：{{ item.source }}</span>
                    </div>
                  </el-timeline-item>
                </el-timeline>
              </el-tab-pane>

              <el-tab-pane label="检查检验">
                <div v-if="reportEvents.length" class="report-list">
                  <div v-for="item in reportEvents" :key="item.id" class="report-card">
                    <div class="report-icon"><el-icon><DocumentChecked /></el-icon></div>
                    <div class="report-copy"><div><strong>{{ item.title }}</strong><el-tag size="small" effect="plain">{{ item.type }}</el-tag></div><p>{{ item.summary }}</p><span>{{ item.date }} · {{ item.source }}</span></div>
                  </div>
                </div>
                <el-empty v-else description="暂无检查检验记录" />
              </el-tab-pane>

              <el-tab-pane label="用药记录">
                <el-table :data="store.activePatient.currentMedications" size="small">
                  <el-table-column prop="name" label="药物名称" min-width="150" />
                  <el-table-column prop="dose" label="剂量" width="90" />
                  <el-table-column prop="frequency" label="频次" width="110" />
                  <el-table-column prop="startDate" label="开始时间" width="115" />
                  <el-table-column prop="status" label="状态" width="75" />
                </el-table>
              </el-tab-pane>
            </el-tabs>
          </section>
        </div>

        <RagChatPanel :key="store.activePatient.id" :patient="store.activePatient" />
      </div>
    </template>
    <el-empty v-else-if="!store.loading" description="未找到患者记录" />
  </div>
</template>

<style scoped>
.detail-page { padding-top: 17px; }
.detail-topline { height: 34px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; color: #8795a4; font-size: 11px; }
.patient-banner { min-height: 90px; margin-bottom: 13px; padding: 15px 18px; display: flex; justify-content: space-between; align-items: center; }
.profile-main { display: flex; align-items: center; gap: 13px; }
.patient-avatar { width: 54px; height: 54px; border-radius: 15px; display: grid; place-items: center; background: linear-gradient(145deg,#dff2ee,#e3edf5); color: #0f766e; font-size: 20px; font-weight: 750; }
.patient-name-row { display: flex; align-items: center; gap: 7px; }
.patient-name-row h2 { margin: 0; color: #18384e; font-size: 20px; }
.profile-main p { margin: 6px 0 0; color: #7d8d9e; font-size: 11px; }
.profile-meta { display: grid; grid-template-columns: repeat(3, minmax(110px,1fr)); gap: 22px; }
.profile-meta div { display: flex; flex-direction: column; gap: 4px; }
.profile-meta span { color: #8b99a8; font-size: 10px; }
.profile-meta strong { color: #40596c; font-size: 11px; font-weight: 600; }
.detail-grid { display: grid; grid-template-columns: minmax(570px, .98fr) minmax(540px, 1.02fr); gap: 14px; align-items: start; }
.patient-column { display: flex; flex-direction: column; gap: 12px; }
.summary-strip { display: grid; grid-template-columns: 1.5fr .72fr .72fr; gap: 10px; }
.summary-card { min-height: 66px; padding: 12px 14px; display: flex; align-items: center; gap: 10px; }
.summary-card .el-icon { width: 31px; height: 31px; border-radius: 8px; background: #edf7f5; color: #0f766e; }
.summary-card > div { min-width: 0; display: flex; flex-direction: column; }
.summary-card span { color: #8a98a7; font-size: 10px; }
.summary-card strong { margin-top: 4px; color: #304a5f; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.patient-info-card { min-height: 550px; padding: 5px 18px 18px; }
.overview-block { margin-bottom: 18px; }
.care-summary { margin: 9px 0 0; background: #f7fafc; color: #536b7f; border-left: 3px solid #73b7aa; line-height: 1.75; font-size: 12px; padding: 10px 12px; border-radius: 0 8px 8px 0; }
.metric-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 9px; margin-top: 10px; }
.metric-item { border: 1px solid #e7edf2; border-radius: 9px; padding: 10px 11px; display: flex; flex-direction: column; }
.metric-item span { color: #7e8e9e; font-size: 10px; }
.metric-item strong { margin: 4px 0 2px; color: #3c5467; font-size: 16px; }
.metric-item strong.warning { color: #ad5b46; }
.metric-item strong.normal { color: #2c7860; }
.metric-item small { font-size: 9px; font-weight: 500; }
.metric-item em { color: #9aa5af; font-size: 9px; font-style: normal; }
.tag-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 9px; }
.timeline { padding-top: 6px; }
.timeline-item { border: 1px solid #e9edf1; border-radius: 8px; padding: 9px 11px; background: #fbfcfd; }
.timeline-item > div { display: flex; justify-content: space-between; align-items: center; }
.timeline-item strong { color: #3a5267; font-size: 12px; }
.timeline-item p { margin: 7px 0 4px; color: #66798b; font-size: 11px; line-height: 1.55; }
.timeline-item span { color: #9aa5af; font-size: 9px; }
.report-list { display: flex; flex-direction: column; gap: 9px; padding-top: 5px; }
.report-card { display: flex; gap: 11px; border: 1px solid #e7edf2; border-radius: 9px; padding: 11px; background: #fbfcfd; }
.report-icon { width: 34px; height: 34px; flex: 0 0 34px; border-radius: 9px; background: #eaf6f4; color: #0f766e; display: grid; place-items: center; }
.report-copy { min-width: 0; flex: 1; }
.report-copy > div { display: flex; justify-content: space-between; align-items: center; }
.report-copy strong { color: #3a5267; font-size: 12px; }
.report-copy p { margin: 6px 0 4px; color: #65798b; font-size: 11px; line-height: 1.5; }
.report-copy span { color: #98a4af; font-size: 9px; }
</style>
