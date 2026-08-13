import type { DoctorProfile, PatientDetail, PatientSummary } from '@/types'

export const mockDoctor: DoctorProfile = {
  id: 'D001',
  name: '王医生',
  department: '综合保障医学中心',
  title: '主治医师',
}

export const mockPatients: PatientSummary[] = [
  { id: 'P10001', name: '张某', gender: '男', age: 67, diagnoses: ['高血压', '2型糖尿病'], lastVisit: '2026-08-08', riskLevel: '高', status: '需关注' },
  { id: 'P10002', name: '李某', gender: '女', age: 58, diagnoses: ['高脂血症', '冠心病'], lastVisit: '2026-08-06', riskLevel: '中', status: '随访中' },
  { id: 'P10003', name: '赵某', gender: '男', age: 72, diagnoses: ['高血压', '慢性肾病'], lastVisit: '2026-08-05', riskLevel: '高', status: '需关注' },
  { id: 'P10004', name: '周某', gender: '女', age: 49, diagnoses: ['甲状腺结节'], lastVisit: '2026-08-03', riskLevel: '低', status: '稳定' },
  { id: 'P10005', name: '陈某', gender: '男', age: 63, diagnoses: ['2型糖尿病'], lastVisit: '2026-07-30', riskLevel: '中', status: '随访中' },
  { id: 'P10006', name: '刘某', gender: '女', age: 70, diagnoses: ['骨质疏松', '高血压'], lastVisit: '2026-07-28', riskLevel: '中', status: '随访中' },
  { id: 'P10007', name: '吴某', gender: '男', age: 54, diagnoses: ['脂肪肝', '高尿酸血症'], lastVisit: '2026-07-26', riskLevel: '低', status: '稳定' },
  { id: 'P10008', name: '孙某', gender: '女', age: 61, diagnoses: ['高血压'], lastVisit: '2026-07-22', riskLevel: '中', status: '随访中' },
]

const sharedDetails: Record<string, Partial<PatientDetail>> = {}

sharedDetails.P10001 = {
  patientNo: 'JD-2026-000128',
  phoneMasked: '138****2186',
  allergies: ['青霉素'],
  chronicDiseases: ['高血压（10年）', '2型糖尿病（5年）', '高脂血症'],
  careSummary: '近三年血压控制仍不稳定，糖化血红蛋白呈缓慢升高趋势；建议重点关注血压、血糖及心血管综合风险。',
  recentMetrics: [
    { name: '血压', value: '155/96', unit: 'mmHg', date: '2026-08-08', status: '偏高' },
    { name: '糖化血红蛋白', value: '8.1', unit: '%', date: '2026-08-08', status: '偏高' },
    { name: '低密度脂蛋白胆固醇', value: '4.1', unit: 'mmol/L', date: '2026-08-08', status: '偏高' },
    { name: '肌酐', value: '92', unit: 'μmol/L', date: '2026-08-08', status: '正常' },
  ],
  currentMedications: [
    { name: '硝苯地平控释片', dose: '30 mg', frequency: '每日一次', startDate: '2024-05-12', status: '当前' },
    { name: '二甲双胍片', dose: '0.5 g', frequency: '每日两次', startDate: '2024-02-18', status: '当前' },
    { name: '阿托伐他汀钙片', dose: '20 mg', frequency: '每晚一次', startDate: '2025-03-06', status: '当前' },
  ],
  timeline: [
    { id: 'E1001', date: '2026-08-08', type: '门诊', title: '慢病随访门诊', summary: '血压 155/96 mmHg，糖化血红蛋白 8.1%，继续慢病综合评估。', source: '门诊记录' },
    { id: 'E1002', date: '2026-08-08', type: '检验', title: '血糖与血脂复查', summary: 'HbA1c 8.1%，LDL-C 4.1 mmol/L，较上次升高。', source: '检验系统' },
    { id: 'E1003', date: '2026-03-11', type: '检查', title: '眼底检查', summary: '未见急性视网膜病变表现，建议按期复查。', source: '检查报告' },
    { id: 'E1004', date: '2025-08-21', type: '门诊', title: '糖尿病随访', summary: 'HbA1c 7.8%，血压 148/91 mmHg。', source: '门诊记录' },
    { id: 'E1005', date: '2024-05-10', type: '门诊', title: '高血压随访', summary: '血压 150/93 mmHg，调整长期监测计划。', source: '门诊记录' },
  ],
}

export function getPatientDetail(id: string): PatientDetail | undefined {
  const summary = mockPatients.find((item) => item.id === id)
  if (!summary) return undefined

  const detail = sharedDetails[id] ?? {
    patientNo: `JD-2026-${id.slice(-5)}`,
    phoneMasked: '13*********',
    allergies: [],
    chronicDiseases: summary.diagnoses,
    careSummary: '当前为演示患者数据，第一版主要用于验证患者结构化信息与医学知识库问答的联合流程。',
    recentMetrics: [
      { name: '血压', value: '132/84', unit: 'mmHg', date: summary.lastVisit, status: '正常' },
      { name: '空腹血糖', value: '6.2', unit: 'mmol/L', date: summary.lastVisit, status: '正常' },
    ],
    currentMedications: [],
    timeline: [
      { id: `${id}-1`, date: summary.lastVisit, type: '门诊', title: '常规随访', summary: '患者完成常规随访与健康状态评估。', source: '门诊记录' },
    ],
  }

  return { ...summary, ...detail } as PatientDetail
}
