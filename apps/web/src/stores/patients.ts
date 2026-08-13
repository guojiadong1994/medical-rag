import { ref } from 'vue'
import { defineStore } from 'pinia'
import { fetchPatientDetail, fetchPatients } from '@/api/patients'
import type { PatientDetail, PatientSummary } from '@/types'

export const usePatientsStore = defineStore('patients', () => {
  const patients = ref<PatientSummary[]>([])
  const activePatient = ref<PatientDetail | null>(null)
  const loading = ref(false)

  async function loadPatients() {
    loading.value = true
    try {
      patients.value = await fetchPatients()
    } finally {
      loading.value = false
    }
  }

  async function loadPatientDetail(id: string) {
    loading.value = true
    try {
      activePatient.value = await fetchPatientDetail(id)
    } finally {
      loading.value = false
    }
  }

  return { patients, activePatient, loading, loadPatients, loadPatientDetail }
})
