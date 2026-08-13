<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import DoctorLayout from '@/layouts/DoctorLayout.vue'
import { usePatientsStore } from '@/stores/patients'
import type { RiskLevel } from '@/types'

const router = useRouter()
const store = usePatientsStore()
const keyword = ref('')
const risk = ref<'全部' | RiskLevel>('全部')

onMounted(() => store.loadPatients())

const filteredPatients = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return store.patients.filter((patient) => {
    const matchesText = !text || patient.name.toLowerCase().includes(text) || patient.id.toLowerCase().includes(text) || patient.diagnoses.some((item) => item.includes(text))
    const matchesRisk = risk.value === '全部' || patient.riskLevel === risk.value
    return matchesText && matchesRisk
  })
})

function riskTag(level: RiskLevel) {
  return level === '高' ? 'danger' : level === '中' ? 'warning' : 'success'
}
</script>

<template>
  <DoctorLayout>
    <div class="page-container">
      <div class="title-row">
        <div>
          <h1 class="page-title">患者列表</h1>
          <div class="page-subtitle">选择患者后进入患者详情与医学知识库辅助问答工作台。</div>
        </div>
        <div class="stats">
          <div><span>患者总数</span><strong>{{ store.patients.length }}</strong></div>
          <div><span>需重点关注</span><strong class="danger">{{ store.patients.filter(p => p.riskLevel === '高').length }}</strong></div>
        </div>
      </div>

      <section class="card list-card">
        <div class="toolbar">
          <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索患者姓名、编号或疾病" style="width: 360px" />
          <el-segmented v-model="risk" :options="['全部', '高', '中', '低']" />
        </div>

        <el-table v-loading="store.loading" :data="filteredPatients" size="large" stripe>
          <el-table-column label="患者" min-width="155">
            <template #default="{ row }">
              <div class="patient-cell">
                <el-avatar :size="34" :icon="UserFilled" />
                <div><strong>{{ row.name }}</strong><span>{{ row.id }}</span></div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="gender" label="性别" width="80" />
          <el-table-column prop="age" label="年龄" width="80" />
          <el-table-column label="主要疾病" min-width="270">
            <template #default="{ row }">
              <div class="diagnoses"><el-tag v-for="item in row.diagnoses" :key="item" effect="plain">{{ item }}</el-tag></div>
            </template>
          </el-table-column>
          <el-table-column prop="lastVisit" label="最近就诊" width="135" />
          <el-table-column label="风险" width="100">
            <template #default="{ row }"><el-tag :type="riskTag(row.riskLevel)" effect="light">{{ row.riskLevel }}风险</el-tag></template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="110" />
          <el-table-column label="操作" width="120" align="right">
            <template #default="{ row }"><el-button type="primary" link @click="router.push(`/patients/${row.id}`)">进入工作台</el-button></template>
          </el-table-column>
        </el-table>
      </section>
      <div class="mock-tip">当前患者均为模拟数据，仅用于第一版功能验证。</div>
    </div>
  </DoctorLayout>
</template>

<style scoped>
.title-row { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 22px; }
.stats { display: flex; gap: 12px; }
.stats > div { width: 128px; height: 58px; border: 1px solid #e4eaf0; border-radius: 10px; background: white; padding: 8px 12px; display: flex; flex-direction: column; }
.stats span { color: #8391a1; font-size: 11px; }
.stats strong { color: #28455c; font-size: 19px; margin-top: 3px; }
.stats strong.danger { color: #bd4d48; }
.list-card { overflow: hidden; }
.toolbar { height: 70px; display: flex; align-items: center; gap: 16px; padding: 0 18px; border-bottom: 1px solid #e7edf2; }
.patient-cell { display: flex; align-items: center; gap: 10px; }
.patient-cell > div { display: flex; flex-direction: column; }
.patient-cell strong { color: #263f54; font-size: 14px; }
.patient-cell span { color: #96a1ad; font-size: 11px; margin-top: 2px; }
.diagnoses { display: flex; flex-wrap: wrap; gap: 6px; }
.mock-tip { text-align: center; margin-top: 13px; color: #9aa5b1; font-size: 11px; }
</style>
