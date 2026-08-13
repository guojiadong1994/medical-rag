<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { ChatDotRound, Delete, Document, Promotion, UserFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { askMedicalKnowledge } from '@/api/rag'
import type { ChatMessage, PatientDetail } from '@/types'

const props = defineProps<{ patient: PatientDetail }>()
const question = ref('')
const sending = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const messages = ref<ChatMessage[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content: `已加载 ${props.patient.name} 的患者资料。你可以围绕患者当前疾病、历次指标、用药和检查记录提问。下一阶段接入真实医学知识库后，回答会同时给出患者依据与指南依据。`,
    createdAt: new Date().toISOString(),
  },
])

const suggestions = computed(() => [
  '这个患者目前最值得关注的问题是什么？',
  '结合最近几次指标，哪些趋势需要重点关注？',
  '当前用药与既往疾病需要关注哪些方面？',
])

async function sendQuestion(text?: string) {
  const value = (text ?? question.value).trim()
  if (!value || sending.value) return

  messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: value, createdAt: new Date().toISOString() })
  question.value = ''
  sending.value = true
  await scrollBottom()

  try {
    const answer = await askMedicalKnowledge(props.patient, value)
    messages.value.push(answer)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '问答请求失败')
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

function clearMessages() {
  messages.value = messages.value.slice(0, 1)
}

async function scrollBottom() {
  await nextTick()
  if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
}
</script>

<template>
  <section class="rag-panel card">
    <div class="rag-header">
      <div>
        <div class="rag-title"><el-icon><ChatDotRound /></el-icon> 医学知识库辅助问答</div>
        <div class="rag-status"><span></span> 患者资料已加载 · 知识库接口待接入</div>
      </div>
      <el-button text :icon="Delete" @click="clearMessages">清空会话</el-button>
    </div>

    <div ref="scrollRef" class="message-list">
      <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
        <div class="avatar" :class="message.role">
          <el-icon><UserFilled v-if="message.role === 'user'" /><ChatDotRound v-else /></el-icon>
        </div>
        <div class="message-body">
          <div class="message-name">{{ message.role === 'user' ? '医生' : '医疗知识助手' }}</div>
          <div class="message-bubble">{{ message.content }}</div>

          <div v-if="message.evidences?.length" class="evidence-grid">
            <div v-for="evidence in message.evidences" :key="evidence.id" class="evidence-card">
              <div class="evidence-top">
                <span class="evidence-kind">{{ evidence.kind }}</span>
                <el-icon><Document /></el-icon>
              </div>
              <strong>{{ evidence.title }}</strong>
              <p>{{ evidence.excerpt }}</p>
              <span class="evidence-source">来源：{{ evidence.source }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="sending" class="message-row assistant">
        <div class="avatar assistant"><el-icon><ChatDotRound /></el-icon></div>
        <div class="typing">正在读取患者资料并检索医学知识<span>...</span></div>
      </div>
    </div>

    <div class="suggestion-list">
      <button v-for="item in suggestions" :key="item" @click="sendQuestion(item)">{{ item }}</button>
    </div>

    <div class="composer">
      <el-input
        v-model="question"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 4 }"
        resize="none"
        maxlength="500"
        show-word-limit
        placeholder="请输入关于当前患者的问题，例如：结合最近三年的血压和血糖变化，有哪些值得关注的问题？"
        @keydown.meta.enter.prevent="sendQuestion()"
        @keydown.ctrl.enter.prevent="sendQuestion()"
      />
      <div class="composer-footer">
        <span>回答仅用于医生辅助分析，最终诊疗判断由临床医生完成。</span>
        <el-button type="primary" :icon="Promotion" :loading="sending" @click="sendQuestion()">发送</el-button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rag-panel { height: calc(100vh - 126px); min-height: 720px; display: flex; flex-direction: column; overflow: hidden; }
.rag-header { height: 74px; flex: 0 0 74px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; border-bottom: 1px solid #e8edf2; }
.rag-title { color: #17364b; font-weight: 750; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.rag-title .el-icon { color: #0f766e; }
.rag-status { font-size: 12px; color: #7c8da0; margin-top: 7px; }
.rag-status span { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #2d9f78; margin-right: 5px; }
.message-list { flex: 1; overflow-y: auto; padding: 22px 22px 12px; background: linear-gradient(180deg, #fbfcfe 0%, #f8fafc 100%); }
.message-row { display: flex; gap: 11px; margin-bottom: 22px; }
.message-row.user { flex-direction: row-reverse; }
.avatar { width: 34px; height: 34px; flex: 0 0 34px; border-radius: 10px; display: grid; place-items: center; }
.avatar.assistant { background: #e6f4f1; color: #0f766e; }
.avatar.user { background: #eaf0f7; color: #395873; }
.message-body { max-width: 84%; }
.message-row.user .message-body { text-align: right; }
.message-name { font-size: 11px; color: #8594a5; margin: 0 0 5px 2px; }
.message-bubble { white-space: pre-line; text-align: left; background: #fff; color: #314457; border: 1px solid #e5ebf1; border-radius: 4px 14px 14px 14px; padding: 13px 15px; line-height: 1.72; font-size: 14px; box-shadow: 0 3px 13px rgba(42, 64, 87, .04); }
.user .message-bubble { background: #0f766e; color: white; border-color: #0f766e; border-radius: 14px 4px 14px 14px; }
.evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 10px; margin-top: 10px; text-align: left; }
.evidence-card { border: 1px solid #e1e9ee; background: #fff; border-radius: 10px; padding: 11px 12px; }
.evidence-top { display: flex; justify-content: space-between; color: #8190a0; font-size: 11px; }
.evidence-kind { color: #0f766e; background: #ecf8f5; border-radius: 999px; padding: 2px 7px; }
.evidence-card strong { display: block; color: #31475b; font-size: 12px; margin-top: 8px; }
.evidence-card p { font-size: 12px; color: #687b8e; line-height: 1.55; margin: 6px 0; }
.evidence-source { font-size: 10px; color: #93a0ae; }
.typing { margin-top: 7px; color: #7f8e9d; font-size: 13px; }
.suggestion-list { padding: 8px 20px 0; background: #fff; display: flex; flex-wrap: wrap; gap: 8px; }
.suggestion-list button { border: 1px solid #dce6e7; background: #f8fbfb; color: #47616a; font-size: 12px; border-radius: 999px; padding: 7px 11px; cursor: pointer; transition: .2s; }
.suggestion-list button:hover { color: #0f766e; border-color: #9bcac4; background: #f0f8f6; }
.composer { padding: 13px 18px 16px; background: #fff; }
.composer-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 9px; color: #909dad; font-size: 11px; }
</style>
