import type { ChatMessage, PatientDetail } from '@/types'

export async function mockAsk(patient: PatientDetail, question: string): Promise<ChatMessage> {
  await new Promise((resolve) => setTimeout(resolve, 850))

  const content = patient.id === 'P10001'
    ? `结合当前患者结构化记录，近三年血压仍持续偏高，同时糖化血红蛋白由既往 7.8% 升至 8.1%，并伴有低密度脂蛋白胆固醇偏高。当前最值得关注的是血压、血糖和血脂的综合控制情况，以及长期心血管风险。\n\n当前页面为第一版界面演示，知识库尚未接入真实指南，因此这里只展示未来问答结果的结构，不作为临床诊疗依据。`
    : `已读取 ${patient.name} 的当前结构化患者资料。针对“${question}”，第一版将先汇总患者事实，再从医学知识库检索相关指南片段，最终生成带来源引用的辅助分析。当前为界面演示数据，尚未接入真实知识库。`

  return {
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content,
    createdAt: new Date().toISOString(),
    evidences: [
      {
        id: 'patient-evidence-1',
        kind: '患者依据',
        title: `${patient.lastVisit} 最近一次随访`,
        source: '模拟患者数据库',
        excerpt: patient.careSummary,
      },
      {
        id: 'kb-evidence-1',
        kind: '知识库依据',
        title: '医学指南检索结果占位',
        source: '知识库尚未接入',
        excerpt: '下一阶段接入真实医学 PDF 后，这里展示命中的指南名称、章节、页码和原文片段。',
      },
    ],
  }
}
