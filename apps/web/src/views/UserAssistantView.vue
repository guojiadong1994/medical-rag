<template>
  <div class="assistant-layout">
    <aside class="chat-sidebar">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px">
        <div class="brand-mark" style="width:38px;height:38px;font-size:16px">AI</div>
        <div>
          <strong style="font-size:14px">AI 健康助手</strong>
          <div class="muted small" style="margin-top:3px">个人医疗数据 + 医学知识</div>
        </div>
      </div>
      <div class="muted small" style="margin-bottom:10px">你可以这样问</div>
      <button v-for="question in aiQuickQuestions" :key="question" class="quick-question" @click="send(question)">{{ question }}</button>
      <el-alert title="健康助手用于医疗信息理解与健康管理辅助，不替代医生诊断与治疗。" type="info" :closable="false" show-icon style="margin-top:18px" />
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <el-avatar :size="38" style="background:#0f766e">智</el-avatar>
        <div>
          <strong>健康信息智能解读</strong>
          <div class="muted small" style="margin-top:3px">回答将优先引用你的医疗记录，并补充权威医学知识依据</div>
        </div>
      </header>

      <div class="chat-messages" ref="messageContainer">
        <div class="message assistant">
          <el-avatar :size="30" style="background:#0f766e">智</el-avatar>
          <div class="message-bubble">你好，我可以帮助你理解已同步的医疗记录、检验检查结果和用药信息。你可以直接问“我最近的 LDL-C 怎么样”或“帮我解释最近一次血液检查”。</div>
        </div>

        <div v-for="(message, index) in messages" :key="index" class="message" :class="message.role">
          <el-avatar :size="30" :style="message.role === 'assistant' ? 'background:#0f766e' : 'background:#617579'">
            {{ message.role === 'assistant' ? '智' : '我' }}
          </el-avatar>
          <div class="message-bubble">
            <div style="white-space:pre-line">{{ message.content }}</div>
            <div v-if="message.citations?.length" class="citation-box">
              <strong style="font-size:11px">参考来源</strong>
              <span v-for="citation in message.citations" :key="citation">• {{ citation }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input v-model="input" size="large" placeholder="输入你想了解的健康问题" @keyup.enter="submit" />
        <el-button type="primary" size="large" :loading="thinking" @click="submit">发送</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { aiQuickQuestions } from '@/data/health'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  citations?: string[]
}

const input = ref('')
const thinking = ref(false)
const messages = ref<ChatMessage[]>([])
const messageContainer = ref<HTMLElement | null>(null)

onMounted(() => {
  const prefill = sessionStorage.getItem('assistant-prefill')
  if (prefill) {
    sessionStorage.removeItem('assistant-prefill')
    send(prefill)
  }
})

function buildAnswer(question: string): ChatMessage {
  const q = question.toLowerCase()
  if (q.includes('ldl') || q.includes('血脂')) {
    return {
      role: 'assistant',
      content: '从已同步的检验记录看，你的 LDL-C 呈持续下降趋势：2026年3月为 4.20 mmol/L，5月为 3.80 mmol/L，8月为 3.40 mmol/L。整体较3月下降约19%。\n\n7月心血管内科复诊记录显示你仍在使用阿托伐他汀钙片 20 mg，每晚一次，因此规律用药和生活方式管理可能共同参与了这一变化。当前数值仍建议结合个人心血管风险水平继续随访。',
      citations: ['2026-08-12 北京大学第三医院 · 血脂及糖代谢相关检验', '2026-07-20 北京大学第三医院 · 心血管内科复诊', '《中国血脂管理指南（2023年）》'],
    }
  }
  if (q.includes('血液') || q.includes('检验')) {
    return {
      role: 'assistant',
      content: '最近一次血液相关检验记录来自 2026年8月12日。LDL-C 为 3.40 mmol/L，仍需关注；HDL-C 为 1.21 mmol/L，甘油三酯 1.36 mmol/L，HbA1c 为 5.8%。\n\n与3月相比，LDL-C 已明显下降，糖化血红蛋白目前保持稳定。建议按既有复诊安排继续监测血脂，并结合医生给出的治疗目标判断是否达到个体化控制要求。',
      citations: ['2026-08-12 北京大学第三医院 · 检验科', '2026-03-04 北京大学第三医院 · 年度健康体检', '《中国血脂管理指南（2023年）》'],
    }
  }
  if (q.includes('药') || q.includes('服用')) {
    return {
      role: 'assistant',
      content: '当前健康档案中记录了两项持续用药：\n1. 阿托伐他汀钙片 20 mg，每晚一次，用于血脂管理。\n2. 苯磺酸氨氯地平片 5 mg，每日一次，用于血压管理。\n\n最近处方记录日期均为 2026年7月20日。请以实际医嘱和最新处方为准，不要自行停药或调整剂量。',
      citations: ['2026-07-20 北京大学第三医院 · 心血管内科处方', '常用心血管药物临床用药参考'],
    }
  }
  if (q.includes('ct') || q.includes('胸部')) {
    return {
      role: 'assistant',
      content: '2026年5月24日的胸部 CT 记录显示：双肺未见明显实变影，纵隔未见明显肿大淋巴结，心影大小未见明显异常。影像意见为“未见明显急性胸部异常”。\n\n这表示该次影像检查没有发现明确的急性胸部异常，但影像结果仍需结合症状、既往史和临床检查综合判断。',
      citations: ['2026-05-24 北京协和医院 · 放射科胸部CT检查'],
    }
  }
  return {
    role: 'assistant',
    content: '根据近期已同步的医疗记录，你目前最需要持续关注的是血脂和血压管理。血压较前改善，LDL-C 也呈下降趋势；HbA1c 保持稳定。近期没有记录到明显急性异常。\n\n如果你希望更具体一些，可以继续问某项指标、某次检查或当前用药，我会结合对应医疗记录进行解释。',
    citations: ['2026-08-12 北京大学第三医院 · 血脂及糖代谢相关检验', '2026-07-20 北京大学第三医院 · 心血管内科复诊'],
  }
}

async function send(question: string) {
  if (!question.trim() || thinking.value) return
  messages.value.push({ role: 'user', content: question.trim() })
  input.value = ''
  thinking.value = true
  await nextTick()
  messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
  window.setTimeout(async () => {
    messages.value.push(buildAnswer(question))
    thinking.value = false
    await nextTick()
    messageContainer.value?.scrollTo({ top: messageContainer.value.scrollHeight, behavior: 'smooth' })
  }, 450)
}

function submit() {
  send(input.value)
}
</script>
