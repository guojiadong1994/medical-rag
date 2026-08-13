<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ChatDotRound, Delete, Document, Promotion, UserFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { askKnowledge } from '@/api/rag'
import type { ChatMessage } from '@/types'

const question = ref('')
const sending = ref(false)
const scrollRef = ref<HTMLElement | null>(null)
const messages = ref<ChatMessage[]>([
  { id: 'welcome', role: 'assistant', content: '请输入需要查询的医学问题。系统将从医学知识库检索相关内容，并在回答中展示原始资料依据。', createdAt: new Date().toISOString() },
])
const suggestions = ['高血压患者长期管理需要关注哪些方面？', '2型糖尿病患者随访通常关注哪些指标？', '老年慢病患者用药管理需要注意哪些问题？']

async function sendQuestion(text?: string) {
  const value = (text ?? question.value).trim()
  if (!value || sending.value) return
  messages.value.push({ id: `user-${Date.now()}`, role: 'user', content: value, createdAt: new Date().toISOString() })
  question.value = ''
  sending.value = true
  await scrollBottom()
  try {
    messages.value.push(await askKnowledge(value))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '问答服务暂不可用')
  } finally {
    sending.value = false
    await scrollBottom()
  }
}

function clearMessages() { messages.value = messages.value.slice(0, 1) }
async function scrollBottom() { await nextTick(); if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight }
</script>

<template>
  <div class="page-container knowledge-chat-page">
    <div class="title-row"><div><h1 class="page-title">医学知识问答</h1><div class="page-subtitle">直接检索医学知识库，不绑定具体患者档案。</div></div></div>
    <section class="card chat-card">
      <div class="chat-header"><div><strong><el-icon><ChatDotRound /></el-icon> 医学知识助手</strong><span>知识检索与来源引用</span></div><el-button text :icon="Delete" @click="clearMessages">清空会话</el-button></div>
      <div ref="scrollRef" class="messages">
        <div v-for="message in messages" :key="message.id" class="message-row" :class="message.role">
          <div class="avatar" :class="message.role"><el-icon><UserFilled v-if="message.role === 'user'" /><ChatDotRound v-else /></el-icon></div>
          <div class="message-body"><div class="name">{{ message.role === 'user' ? '医生' : '医学知识助手' }}</div><div class="bubble">{{ message.content }}</div>
            <div v-if="message.evidences?.length" class="evidence-list"><div v-for="item in message.evidences" :key="item.id" class="evidence"><div><span>{{ item.kind }}</span><el-icon><Document /></el-icon></div><strong>{{ item.title }}</strong><p>{{ item.excerpt }}</p><em>来源：{{ item.source }}</em></div></div>
          </div>
        </div>
        <div v-if="sending" class="message-row assistant"><div class="avatar assistant"><el-icon><ChatDotRound /></el-icon></div><div class="typing">正在检索医学知识...</div></div>
      </div>
      <div class="suggestions"><button v-for="item in suggestions" :key="item" @click="sendQuestion(item)">{{ item }}</button></div>
      <div class="composer"><el-input v-model="question" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" resize="none" maxlength="500" show-word-limit placeholder="请输入医学知识问题" @keydown.meta.enter.prevent="sendQuestion()" @keydown.ctrl.enter.prevent="sendQuestion()" /><div class="composer-footer"><span>回答用于临床知识辅助，请结合患者实际情况进行专业判断。</span><el-button type="primary" :icon="Promotion" :loading="sending" @click="sendQuestion()">发送</el-button></div></div>
    </section>
  </div>
</template>

<style scoped>
.knowledge-chat-page { padding-top: 24px; }
.title-row { margin-bottom: 18px; }
.chat-card { height: calc(100vh - 154px); min-height: 700px; display: flex; flex-direction: column; overflow: hidden; }
.chat-header { height: 68px; flex: 0 0 68px; padding: 0 20px; border-bottom: 1px solid #e8edf2; display: flex; justify-content: space-between; align-items: center; }
.chat-header > div { display: flex; flex-direction: column; gap: 4px; }
.chat-header strong { display: flex; align-items: center; gap: 7px; color: #29465b; font-size: 14px; }
.chat-header strong .el-icon { color: #0f766e; }
.chat-header span { color: #909eac; font-size: 10px; }
.messages { flex: 1; overflow-y: auto; padding: 22px 8%; background: #fafcfd; }
.message-row { display: flex; gap: 10px; margin-bottom: 20px; }
.message-row.user { flex-direction: row-reverse; }
.avatar { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; flex: 0 0 34px; }
.avatar.assistant { background: #e7f5f2; color: #0f766e; }
.avatar.user { background: #eaf0f7; color: #395873; }
.message-body { max-width: 76%; }
.message-row.user .message-body { text-align: right; }
.name { color: #8997a5; font-size: 10px; margin-bottom: 5px; }
.bubble { white-space: pre-line; text-align: left; border: 1px solid #e5ebf1; border-radius: 4px 14px 14px 14px; background: #fff; color: #314457; padding: 12px 14px; font-size: 13px; line-height: 1.75; }
.user .bubble { background: #0f766e; border-color: #0f766e; color: #fff; border-radius: 14px 4px 14px 14px; }
.evidence-list { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 9px; margin-top: 9px; text-align: left; }
.evidence { border: 1px solid #e1e9ee; background: #fff; border-radius: 9px; padding: 10px; }
.evidence > div { display: flex; justify-content: space-between; color: #8190a0; font-size: 10px; }
.evidence > div span { color: #0f766e; }
.evidence strong { display: block; color: #31475b; font-size: 11px; margin-top: 7px; }
.evidence p { color: #687b8e; font-size: 11px; line-height: 1.55; }
.evidence em { color: #93a0ae; font-size: 9px; font-style: normal; }
.typing { margin-top: 7px; color: #7f8e9d; font-size: 12px; }
.suggestions { padding: 8px 18px 0; display: flex; gap: 7px; flex-wrap: wrap; }
.suggestions button { border: 1px solid #dce6e7; background: #f8fbfb; color: #47616a; border-radius: 999px; padding: 6px 10px; font-size: 11px; cursor: pointer; }
.composer { padding: 12px 18px 15px; }
.composer-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; color: #909dad; font-size: 10px; }
</style>
