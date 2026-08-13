export type RiskLevel = '高' | '中' | '低'

export interface DoctorProfile {
  id: string
  name: string
  department: string
  title: string
}

export interface PatientSummary {
  id: string
  name: string
  gender: '男' | '女'
  age: number
  diagnoses: string[]
  lastVisit: string
  riskLevel: RiskLevel
  status: '随访中' | '稳定' | '需关注'
}

export interface MetricRecord {
  name: string
  value: string
  unit?: string
  date: string
  status: '正常' | '偏高' | '偏低' | '需关注'
}

export interface MedicationRecord {
  name: string
  dose: string
  frequency: string
  startDate: string
  status: '当前' | '停用'
}

export interface MedicalEvent {
  id: string
  date: string
  type: '门诊' | '检验' | '检查' | '用药' | '住院'
  title: string
  summary: string
  source: string
}

export interface PatientDetail extends PatientSummary {
  patientNo: string
  phoneMasked: string
  allergies: string[]
  chronicDiseases: string[]
  currentMedications: MedicationRecord[]
  recentMetrics: MetricRecord[]
  timeline: MedicalEvent[]
  careSummary: string
}

export interface EvidenceItem {
  id: string
  title: string
  source: string
  excerpt: string
  kind: '患者依据' | '知识库依据'
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  evidences?: EvidenceItem[]
}
