<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh, Search, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { usePatientsStore } from '@/stores/patients'
import type { PatientSummary, RiskLevel } from '@/types'

const router = useRouter()
const store = usePatientsStore()
const keyword = ref('')
const risk = ref<'全部' | RiskLevel>('全部')
const gender = ref<'全部' | '男' | '女'>('全部')
const status = ref('全部')
const page = ref(1)
const pageSize = ref(6)

onMounted(() => store.loadPatients())

const filteredPatients = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return store.patients.filter((patient) => {
    const matchesText = !text || patient.name.toLowerCase().includes(text) || patient.id.toLowerCase().includes(text) || patient.patientNo?.toLowerCase().includes(text) || patient.diagnoses.some((item) => item.toLowerCase().includes(text))
    const matchesRisk = risk.value === '全部' || patient.riskLevel === risk.value
    const matchesGender = gender.value === '全部' || patient.gender === gender.value
    const matchesStatus = status.value === '全部' || patient.status === status.value
    return matchesText && matchesRisk && matchesGender && matchesStatus
  })
})

const pageRows = computed(() => filteredPatients.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const highRiskCount = computed(() => store.patients.filter((item) => item.riskLevel === '高').length)

function riskTag(level: RiskLevel) {
  return level === '高' ? 'danger' : level === '中' ? 'warning' : 'success'
}

function resetFilters() {
  keyword.value = ''
  risk.value = '全部'
  gender.value = '全部'
  status.value = '全部'
  page.value = 1
}

function openPatient(row: PatientSummary) {
  router.push(`/patients/${row.id}`)
}
</script>

<template>
  <div class="page-container patient-page">
    <div class="title-row">
      <div>
        <h1 class="page-title">患者管理</h1>
        <div class="page-subtitle">查看患者基本资料、慢病情况、历次就诊记录与临床辅助问答。</div>
      </div>
      <div class="stats">
        <div><span>患者总数</span><strong>{{ store.patients.length }}</strong></div>
        <div><span>重点关注</span><strong class="danger">{{ highRiskCount }}</strong></div>
      </div>
    </div>

    <section class="card filter-card">
      <div class="filter-grid">
        <div class="filter-item wide">
          <label>患者检索</label>
          <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="姓名、患者编号或主要诊断" @input="page = 1" />
        </div>
        <div class="filter-item">
          <label>风险等级</label>
          <el-select v-model="risk" @change="page = 1"><el-option v-for="item in ['全部','高','中','低']" :key="item" :label="item" :value="item" /></el-select>
        </div>
        <div class="filter-item">
          <label>性别</label>
          <el-select v-model="gender" @change="page = 1"><el-option v-for="item in ['全部','男','女']" :key="item" :label="item" :value="item" /></el-select>
        </div>
        <div class="filter-item">
          <label>管理状态</label>
          <el-select v-model="status" @change="page = 1"><el-option v-for="item in ['全部','随访中','稳定','需关注']" :key="item" :label="item" :value="item" /></el-select>
        </div>
        <div class="filter-actions">
          <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
        </div>
      </div>
    </section>

    <section class="card list-card">
      <div class="table-title">
        <div><strong>患者列表</strong><span>共 {{ filteredPatients.length }} 条记录</span></div>
      </div>
      <el-table v-loading="store.loading" :data="pageRows" size="large" stripe @row-dblclick="openPatient">
        <el-table-column type="index" label="序号" width="70" align="center" />
        <el-table-column label="患者" min-width="150">
          <template #default="{ row }">
            <div class="patient-cell"><el-avatar :size="34" :icon="UserFilled" /><div><strong>{{ row.name }}</strong><span>{{ row.patientNo || row.id }}</span></div></div>
          </template>
        </el-table-column>
        <el-table-column prop="gender" label="性别" width="72" />
        <el-table-column prop="age" label="年龄" width="72" />
        <el-table-column label="主要诊断" min-width="250">
          <template #default="{ row }"><div class="diagnoses"><el-tag v-for="item in row.diagnoses" :key="item" effect="plain" size="small">{{ item }}</el-tag></div></template>
        </el-table-column>
        <el-table-column prop="lastVisit" label="最近就诊" width="120" />
        <el-table-column label="风险等级" width="100">
          <template #default="{ row }"><el-tag :type="riskTag(row.riskLevel)" effect="light">{{ row.riskLevel }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="管理状态" width="100" />
        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }"><el-button type="primary" link @click="router.push(`/patients/${row.id}`)">查看详情</el-button></template>
        </el-table-column>
      </el-table>
      <div class="pagination-row">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" background layout="total, prev, pager, next" :total="filteredPatients.length" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.patient-page { padding-top: 24px; }
.title-row { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 18px; }
.stats { display: flex; gap: 10px; }
.stats > div { width: 120px; min-height: 56px; background: #fff; border: 1px solid #e5eaf0; border-radius: 10px; padding: 8px 12px; display: flex; flex-direction: column; }
.stats span { color: #8492a1; font-size: 10px; }
.stats strong { color: #29465b; font-size: 19px; margin-top: 3px; }
.stats strong.danger { color: #bd514b; }
.filter-card { margin-bottom: 14px; padding: 16px 18px; }
.filter-grid { display: grid; grid-template-columns: minmax(260px, 1.4fr) repeat(3, minmax(120px,.55fr)) auto; gap: 12px; align-items: end; }
.filter-item { display: flex; flex-direction: column; gap: 7px; }
.filter-item label { color: #718294; font-size: 11px; }
.filter-actions { padding-bottom: 1px; }
.list-card { overflow: hidden; }
.table-title { min-height: 58px; display: flex; align-items: center; padding: 0 18px; border-bottom: 1px solid #e8edf2; }
.table-title > div { display: flex; align-items: baseline; gap: 8px; }
.table-title strong { color: #29465b; font-size: 14px; }
.table-title span { color: #95a0ad; font-size: 10px; }
.patient-cell { display: flex; align-items: center; gap: 10px; }
.patient-cell > div { display: flex; flex-direction: column; gap: 2px; }
.patient-cell strong { color: #2c465a; font-size: 13px; }
.patient-cell span { color: #97a2ae; font-size: 10px; }
.diagnoses { display: flex; flex-wrap: wrap; gap: 5px; }
.pagination-row { min-height: 66px; padding: 0 18px; display: flex; justify-content: flex-end; align-items: center; border-top: 1px solid #edf1f4; }
</style>
