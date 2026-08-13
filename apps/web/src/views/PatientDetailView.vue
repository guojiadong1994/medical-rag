<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowLeft, Calendar, DataAnalysis, DocumentChecked, FirstAidKit, Warning } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import DoctorLayout from '@/layouts/DoctorLayout.vue'
import RagChatPanel from '@/components/RagChatPanel.vue'
import { usePatientsStore } from '@/stores/patients'

const route = useRoute()
const router = useRouter()
const store = usePatientsStore()
const patientId = computed(() => String(route.params.patientId))

onMounted(() => store.loadPatientDetail(patientId.value))

function metricClass(status: string) {
  return status === '正常' ? 'normal' : 'warning'
}
</script>

<template>
  <DoctorLayout>
    <div v-loading="store.loading" class="page-container detail-page">
      <template v-if="store.activePatient">
        <div class="detail-topline">
          <el-button text :icon="ArrowLeft" @click="router.push('/patients')">返回患者列表</el-button>
          <span>当前患者：{{ store.activePatient.name }}（{{ store.activePatient.patientNo }}）</span>
        </div>

        <div class="detail-grid">
          <div class="patient-column">
            <section class="card profile-card">
              <div class="profile-main">
                <div class="patient-avatar">{{ store.activePatient.name.slice(0,1) }}</div>
                <div>
                  <div class="patient-name-row">
                    <h2>{{ store.activePatient.name }}</h2>
                    <el-tag type="warning" effect="light">{{ store.activePatient.riskLevel }}风险</el-tag>
                    <el-tag effect="plain">演示数据</el-tag>
                  </div>
                  <p>{{ store.activePatient.gender }} · {{ store.activePatient.age }}岁 · 患者编号 {{ store.activePatient.patientNo }}</p>
                </div>
              </div>
              <div class="profile-meta">
                <span>最近就诊：{{ store.activePatient.lastVisit }}</span>
                <span>联系方式：{{ store.activePatient.phoneMasked }}</span>
                <span>过敏史：{{ store.activePatient.allergies.join('、') || '未记录' }}</span>
              </div>
            </section>

            <section class="summary-strip">
              <div class="summary-card card">
                <el-icon><Warning /></el-icon><div><span>主要疾病</span><strong>{{ store.activePatient.diagnoses.join('、') }}</strong></div>
              </div>
              <div class="summary-card card">
                <el-icon><FirstAidKit /></el-icon><div><span>当前用药</span><strong>{{ store.activePatient.currentMedications.length }} 种</strong></div>
              </div>
              <div class="summary-card card">
                <el-icon><Calendar /></el-icon><div><span>历史事件</span><strong>{{ store.activePatient.timeline.length }} 条</strong></div>
              </div>
            </section>

            <section class="card patient-info-card">
              <el-tabs>
                <el-tab-pane label="患者概览">
                  <div class="overview-block">
                    <div class="section-title">智能摘要</div>
                    <p class="care-summary">{{ store.activePatient.careSummary }}</p>
                  </div>
                  <div class="overview-block">
                    <div class="section-title">近期关键指标</div>
                    <div class="metric-grid">
                      <div v-for="item in store.activePatient.recentMetrics" :key="item.name" class="metric-item">
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

                <el-tab-pane label="时间线">
                  <el-timeline class="timeline">
                    <el-timeline-item v-for="item in store.activePatient.timeline" :key="item.id" :timestamp="item.date" placement="top">
                      <div class="timeline-item">
                        <div><strong>{{ item.title }}</strong><el-tag size="small" effect="plain">{{ item.type }}</el-tag></div>
                        <p>{{ item.summary }}</p><span>来源：{{ item.source }}</span>
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                </el-tab-pane>

                <el-tab-pane label="当前用药">
                  <el-table :data="store.activePatient.currentMedications" size="small">
                    <el-table-column prop="name" label="药物" min-width="150" />
                    <el-table-column prop="dose" label="剂量" width="90" />
                    <el-table-column prop="frequency" label="频次" width="110" />
                    <el-table-column prop="startDate" label="开始时间" width="115" />
                    <el-table-column prop="status" label="状态" width="70" />
                  </el-table>
                </el-tab-pane>

                <el-tab-pane label="检查与报告">
                  <div class="empty-panel">
                    <el-icon><DocumentChecked /></el-icon>
                    <strong>检查与报告查看器</strong>
                    <span>下一阶段接入真实报告、PDF 与医学影像后，在这里按时间查看。</span>
                  </div>
                </el-tab-pane>
              </el-tabs>
            </section>
          </div>

          <RagChatPanel :key="store.activePatient.id" :patient="store.activePatient" />
        </div>
      </template>
    </div>
  </DoctorLayout>
</template>

<style scoped>
.detail-page { padding-top: 14px; }
.detail-topline { height: 36px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; color: #8493a3; font-size: 12px; }
.detail-grid { display: grid; grid-template-columns: minmax(560px, .92fr) minmax(590px, 1.08fr); gap: 18px; align-items: start; }
.patient-column { display: flex; flex-direction: column; gap: 13px; }
.profile-card { padding: 18px 19px 14px; }
.profile-main { display: flex; align-items: center; gap: 13px; }
.patient-avatar { width: 54px; height: 54px; border-radius: 16px; display: grid; place-items: center; background: linear-gradient(145deg, #dff2ee, #e4eef6); color: #0f766e; font-size: 20px; font-weight: 750; }
.patient-name-row { display: flex; align-items: center; gap: 7px; }
.patient-name-row h2 { margin: 0; color: #18374d; font-size: 20px; }
.profile-main p { margin: 6px 0 0; color: #7d8d9e; font-size: 12px; }
.profile-meta { display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 15px; border-top: 1px solid #edf1f4; padding-top: 12px; color: #66798c; font-size: 11px; }
.summary-strip { display: grid; grid-template-columns: 1.55fr .72fr .72fr; gap: 10px; }
.summary-card { padding: 12px 14px; display: flex; gap: 10px; align-items: center; min-height: 66px; }
.summary-card .el-icon { width: 30px; height: 30px; border-radius: 8px; background: #edf7f5; color: #0f766e; }
.summary-card > div { min-width: 0; display: flex; flex-direction: column; }
.summary-card span { color: #8a98a7; font-size: 10px; }
.summary-card strong { margin-top: 4px; font-size: 12px; color: #304a5f; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.patient-info-card { padding: 5px 18px 18px; min-height: 504px; }
.overview-block { margin-bottom: 18px; }
.care-summary { background: #f7fafc; color: #526a7f; border-left: 3px solid #73b7aa; line-height: 1.75; font-size: 12px; padding: 10px 12px; border-radius: 0 8px 8px 0; }
.metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 9px; margin-top: 10px; }
.metric-item { border: 1px solid #e7edf2; border-radius: 9px; padding: 10px 11px; display: flex; flex-direction: column; }
.metric-item span { color: #7e8e9e; font-size: 10px; }
.metric-item strong { font-size: 16px; margin: 4px 0 2px; color: #3c5467; }
.metric-item strong.warning { color: #ad5b46; }
.metric-item strong.normal { color: #2c7860; }
.metric-item small { font-size: 9px; font-weight: 500; }
.metric-item em { font-size: 9px; color: #9aa5af; font-style: normal; }
.tag-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 9px; }
.timeline { padding-top: 6px; }
.timeline-item { border: 1px solid #e9edf1; border-radius: 8px; padding: 9px 11px; background: #fbfcfd; }
.timeline-item > div { display: flex; justify-content: space-between; align-items: center; }
.timeline-item strong { font-size: 12px; color: #3a5267; }
.timeline-item p { color: #66798b; font-size: 11px; line-height: 1.55; margin: 7px 0 4px; }
.timeline-item span { color: #9aa5af; font-size: 9px; }
.empty-panel { height: 300px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: #8a98a6; }
.empty-panel .el-icon { font-size: 34px; color: #85bdb5; }
.empty-panel strong { color: #486276; }
.empty-panel span { font-size: 11px; }
</style>
