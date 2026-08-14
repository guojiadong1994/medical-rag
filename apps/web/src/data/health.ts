export const healthProfile = {
  name: '郭嘉栋',
  gender: '男',
  age: 27,
  birthday: '1999-03-18',
  height: 176,
  weight: 72.4,
  bmi: 23.4,
  bloodType: 'A型',
  phone: '138****6251',
  healthIssues: [
    { name: '高脂血症', firstRecorded: '2025-02-16', source: '北京大学第三医院 · 健康管理中心' },
    { name: '血压偏高', firstRecorded: '2025-11-08', source: '北京大学第三医院 · 心血管内科' },
  ],
  allergies: [
    { name: '青霉素类', reaction: '皮疹', source: '北京大学第三医院 · 门诊病历' },
  ],
  medications: [
    { name: '阿托伐他汀钙片', dose: '20 mg', frequency: '每晚一次', lastPrescription: '2026-07-20', hospital: '北京大学第三医院' },
    { name: '苯磺酸氨氯地平片', dose: '5 mg', frequency: '每日一次', lastPrescription: '2026-07-20', hospital: '北京大学第三医院' },
  ],
}

export const indicators = [
  {
    key: 'bp', name: '血压', value: '132/86', unit: 'mmHg', status: '较稳定', level: 'warning',
    history: [
      { date: '2026-03-05', value: '138/90' },
      { date: '2026-05-18', value: '134/88' },
      { date: '2026-08-12', value: '132/86' },
    ],
  },
  {
    key: 'ldl', name: 'LDL-C', value: '3.40', unit: 'mmol/L', status: '需关注', level: 'danger',
    history: [
      { date: '2026-03-04', value: '4.20' },
      { date: '2026-05-17', value: '3.80' },
      { date: '2026-08-12', value: '3.40' },
    ],
  },
  {
    key: 'hba1c', name: 'HbA1c', value: '5.8', unit: '%', status: '正常', level: 'success',
    history: [
      { date: '2026-02-18', value: '5.9' },
      { date: '2026-05-17', value: '5.8' },
      { date: '2026-08-12', value: '5.8' },
    ],
  },
  {
    key: 'bmi', name: 'BMI', value: '23.4', unit: 'kg/m²', status: '正常', level: 'success',
    history: [
      { date: '2026-01-10', value: '24.1' },
      { date: '2026-04-15', value: '23.8' },
      { date: '2026-08-01', value: '23.4' },
    ],
  },
]

export type RecordType = '门诊' | '检验' | '检查' | '体检' | '处方'

export interface MedicalRecord {
  id: string
  date: string
  type: RecordType
  title: string
  hospital: string
  department?: string
  summary: string
  detail: string[]
  tags?: string[]
}

export const medicalRecords: MedicalRecord[] = [
  {
    id: 'R20260812001', date: '2026-08-12', type: '检验', title: '血脂及糖代谢相关检验',
    hospital: '北京大学第三医院', department: '检验科',
    summary: 'LDL-C 3.40 mmol/L，较3月下降；HbA1c 5.8%。',
    detail: ['LDL-C：3.40 mmol/L ↑', 'HDL-C：1.21 mmol/L', '甘油三酯：1.36 mmol/L', '总胆固醇：5.08 mmol/L', 'HbA1c：5.8%'],
    tags: ['血脂', '血糖'],
  },
  {
    id: 'R20260720002', date: '2026-07-20', type: '门诊', title: '心血管内科复诊',
    hospital: '北京大学第三医院', department: '心血管内科',
    summary: '血压控制较前改善，继续当前降压方案，并持续进行血脂管理。',
    detail: ['诊断：血压偏高、高脂血症', '血压：133/86 mmHg', '建议：继续规律服药，控制盐摄入，保持有氧运动', '复诊：3个月后'],
    tags: ['心血管', '复诊'],
  },
  {
    id: 'R20260720003', date: '2026-07-20', type: '处方', title: '心血管内科处方',
    hospital: '北京大学第三医院', department: '心血管内科',
    summary: '阿托伐他汀钙片20 mg、苯磺酸氨氯地平片5 mg。',
    detail: ['阿托伐他汀钙片：20 mg，每晚一次', '苯磺酸氨氯地平片：5 mg，每日一次', '处方周期：30天'],
    tags: ['用药'],
  },
  {
    id: 'R20260524004', date: '2026-05-24', type: '检查', title: '胸部CT检查',
    hospital: '北京协和医院', department: '放射科',
    summary: '胸部CT未见明显急性异常，建议结合临床随访。',
    detail: ['双肺纹理清晰，未见明显实变影。', '纵隔未见明显肿大淋巴结。', '心影大小未见明显异常。', '影像意见：未见明显急性胸部异常。'],
    tags: ['影像检查'],
  },
  {
    id: 'R20260517005', date: '2026-05-17', type: '检验', title: '生化检验',
    hospital: '北京大学第三医院', department: '检验科',
    summary: 'LDL-C 3.80 mmol/L，较3月下降0.40 mmol/L。',
    detail: ['LDL-C：3.80 mmol/L ↑', 'HDL-C：1.18 mmol/L', '甘油三酯：1.42 mmol/L', '肌酐：75 μmol/L'],
    tags: ['血脂', '肾功能'],
  },
  {
    id: 'R20260304006', date: '2026-03-04', type: '体检', title: '年度健康体检',
    hospital: '北京大学第三医院', department: '健康管理中心',
    summary: '血脂异常，LDL-C 4.20 mmol/L；建议心血管专科评估与生活方式干预。',
    detail: ['血压：138/90 mmHg', 'LDL-C：4.20 mmol/L ↑', '空腹血糖：5.4 mmol/L', 'BMI：23.9 kg/m²', '建议：控制饮食、规律运动并专科随访'],
    tags: ['年度体检'],
  },
]

export const linkedHospitals = [
  { name: '北京大学第三医院', status: '已关联', lastSync: '2026-08-14 09:32', scopes: ['门诊', '检验', '检查', '处方', '体检'] },
  { name: '北京协和医院', status: '已关联', lastSync: '2026-08-13 18:06', scopes: ['门诊', '检验', '检查'] },
]

export const knowledgeDocuments = [
  { id: 'K001', name: '中国血脂管理指南（2023年）.pdf', category: '临床指南', status: '已索引', chunks: 428, updatedAt: '2026-08-12 10:20', size: '8.6 MB' },
  { id: 'K002', name: '中国高血压防治指南（2024年修订版）.pdf', category: '临床指南', status: '已索引', chunks: 516, updatedAt: '2026-08-10 16:45', size: '11.2 MB' },
  { id: 'K003', name: '中国2型糖尿病防治指南（2024版）.pdf', category: '临床指南', status: '已索引', chunks: 603, updatedAt: '2026-08-08 09:11', size: '14.5 MB' },
  { id: 'K004', name: '常用心血管药物临床用药参考.pdf', category: '用药参考', status: '已索引', chunks: 289, updatedAt: '2026-08-06 14:28', size: '5.2 MB' },
]

export const aiQuickQuestions = [
  '总结一下我最近的健康情况',
  '我的LDL-C最近怎么样？',
  '帮我解释最近一次血液检查',
  '我现在正在服用哪些药？',
]
