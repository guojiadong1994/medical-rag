<template>
  <div class="assistant-layout">
    <aside class="chat-sidebar">
      <div class="assistant-brand-row">
        <div class="brand-mark assistant-brand-mark">AI</div>
        <div>
          <strong class="assistant-brand-title">AI 健康助手</strong>
          <div class="muted small assistant-brand-subtitle">医学知识检索 · 证据可追溯</div>
        </div>
      </div>

      <div class="muted small quick-title">你可以这样问</div>
      <button
        v-for="question in aiQuickQuestions"
        :key="question"
        class="quick-question"
        :disabled="thinking"
        @click="send(question)"
      >
        {{ question }}
      </button>

      <el-alert
        title="健康助手用于医疗信息理解与健康管理辅助，不替代医生诊断与治疗。"
        type="info"
        :closable="false"
        show-icon
        class="assistant-safety-alert"
      />
    </aside>

    <section class="chat-main">
      <header class="chat-header">
        <el-avatar :size="38" class="assistant-avatar">智</el-avatar>
        <div class="chat-header-copy">
          <strong>健康信息智能解读</strong>
          <div class="muted small chat-header-subtitle">回答基于当前医疗知识库，并展示实际引用的文件、页码与章节</div>
        </div>
      </header>

      <div ref="messageContainer" class="chat-messages">
        <div class="message assistant">
          <el-avatar :size="30" class="assistant-avatar">智</el-avatar>
          <div class="message-bubble welcome-bubble">
            你好，我已经接入医疗知识库。你可以直接询问指南中的诊断阈值、疾病分级、检查项目、治疗原则等内容。
          </div>
        </div>

        <div
          v-for="(message, index) in messages"
          :key="index"
          class="message"
          :class="message.role"
        >
          <el-avatar
            :size="30"
            :class="message.role === 'assistant' ? 'assistant-avatar' : 'user-avatar'"
          >
            {{ message.role === 'assistant' ? '智' : '我' }}
          </el-avatar>

          <div class="message-bubble">
            <div
              v-if="message.role === 'assistant'"
              class="assistant-answer-content"
              v-html="renderAssistantText(message.content)"
            />
            <div v-else class="user-message-content">{{ message.content }}</div>

            <div v-if="message.sources?.length" class="citation-box">
              <div class="citation-heading">
                <strong>参考来源</strong>
                <span v-if="citedSources(message).length" class="citation-count">
                  {{ citedSources(message).length }} 条已用于回答
                </span>
              </div>

              <div
                v-for="source in citedSources(message)"
                :key="source.citation_id"
                class="source-detail cited-source"
              >
                <div class="source-title-row">
                  <span class="source-id">{{ source.citation_id }}</span>
                  <span class="source-name" :title="source.source_file">{{ source.source_file }}</span>
                  <span class="source-page">
                    第{{ source.page_start === source.page_end ? source.page_start : `${source.page_start}-${source.page_end}` }}页
                  </span>
                </div>
                <div v-if="source.section" class="source-section" :title="source.section">{{ source.section }}</div>
                <div v-if="source.text" class="source-excerpt">{{ cleanPlainText(source.text) }}</div>
              </div>

              <details v-if="supplementalSources(message).length" class="supplemental-sources">
                <summary>查看其他 {{ supplementalSources(message).length }} 条检索证据</summary>
                <div
                  v-for="source in supplementalSources(message)"
                  :key="source.citation_id"
                  class="source-detail supplemental-source"
                >
                  <div class="source-title-row">
                    <span class="source-id">{{ source.citation_id }}</span>
                    <span class="source-name" :title="source.source_file">{{ source.source_file }}</span>
                    <span class="source-page">
                      第{{ source.page_start === source.page_end ? source.page_start : `${source.page_start}-${source.page_end}` }}页
                    </span>
                  </div>
                  <div v-if="source.section" class="source-section" :title="source.section">{{ source.section }}</div>
                  <div v-if="source.text" class="source-excerpt">{{ cleanPlainText(source.text) }}</div>
                </div>
              </details>
            </div>
          </div>
        </div>

        <div v-if="thinking" class="message assistant thinking-message">
          <el-avatar :size="30" class="assistant-avatar">智</el-avatar>
          <div class="message-bubble thinking-bubble">
            <div class="thinking-row">
              <span class="thinking-spinner" aria-hidden="true" />
              <div>
                <div class="thinking-title">{{ thinkingText }}</div>
                <div class="muted small thinking-subtitle">正在基于知识库处理，请稍候 · {{ elapsedSeconds }} 秒</div>
              </div>
            </div>
            <div class="thinking-dots" aria-hidden="true"><span /><span /><span /></div>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="input"
          size="large"
          :disabled="thinking"
          placeholder="输入你想了解的医学知识问题"
          @keyup.enter="submit"
        />
        <el-button type="primary" size="large" :disabled="thinking || !input.trim()" @click="submit">
          {{ thinking ? '处理中' : '发送' }}
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { aiQuickQuestions } from '@/data/health'
import { apiFetch } from '@/api/client'

interface Source {
  citation_id: string
  source_file: string
  page_start: number
  page_end: number
  section?: string | null
  used_in_answer: boolean
  text?: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

interface RagResponse {
  answer: string
  abstained: boolean
  sources: Source[]
  diagnostics: {
    grounding_status: string
    total_tokens?: number | null
  }
}

const input = ref('')
const thinking = ref(false)
const messages = ref<ChatMessage[]>([])
const messageContainer = ref<HTMLElement | null>(null)
const thinkingText = ref('正在分析问题…')
const elapsedSeconds = ref(0)
let elapsedTimer: number | undefined
let stageTimer1: number | undefined
let stageTimer2: number | undefined

onMounted(() => {
  const prefill = sessionStorage.getItem('assistant-prefill')
  if (prefill) {
    sessionStorage.removeItem('assistant-prefill')
    void send(prefill)
  }
})

onBeforeUnmount(() => stopThinkingTimers())

function startThinkingTimers() {
  elapsedSeconds.value = 0
  thinkingText.value = '正在分析问题…'
  stopThinkingTimers()
  const startedAt = Date.now()
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value = Math.max(1, Math.floor((Date.now() - startedAt) / 1000))
  }, 500)
  stageTimer1 = window.setTimeout(() => {
    thinkingText.value = '正在检索知识库并筛选相关证据…'
  }, 1800)
  stageTimer2 = window.setTimeout(() => {
    thinkingText.value = '正在核对证据并组织回答…'
  }, 6500)
}

function stopThinkingTimers() {
  if (elapsedTimer !== undefined) window.clearInterval(elapsedTimer)
  if (stageTimer1 !== undefined) window.clearTimeout(stageTimer1)
  if (stageTimer2 !== undefined) window.clearTimeout(stageTimer2)
  elapsedTimer = undefined
  stageTimer1 = undefined
  stageTimer2 = undefined
}

async function scrollToBottom() {
  await nextTick()
  messageContainer.value?.scrollTo({
    top: messageContainer.value.scrollHeight,
    behavior: 'smooth',
  })
}

async function send(question: string) {
  const normalized = question.trim()
  if (!normalized || thinking.value) return

  messages.value.push({ role: 'user', content: normalized })
  input.value = ''
  thinking.value = true
  startThinkingTimers()
  await scrollToBottom()

  try {
    const result = await apiFetch<RagResponse>('/api/v1/me/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({ question: normalized }),
    })
    messages.value.push({
      role: 'assistant',
      content: cleanPlainText(result.answer),
      sources: result.sources,
    })
  } catch (error) {
    const text = error instanceof Error ? error.message : '知识库问答失败'
    ElMessage.error(text)
    messages.value.push({
      role: 'assistant',
      content: `当前知识库问答暂时不可用。\n\n${cleanPlainText(text)}`,
    })
  } finally {
    thinking.value = false
    stopThinkingTimers()
    await scrollToBottom()
  }
}

function submit() {
  void send(input.value)
}

function citedSources(message: ChatMessage): Source[] {
  return (message.sources ?? []).filter((item) => item.used_in_answer)
}

function supplementalSources(message: ChatMessage): Source[] {
  return (message.sources ?? []).filter((item) => !item.used_in_answer)
}

function cleanPlainText(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/\uFFFD/g, '')
    .replace(/[\u200B-\u200D\uFEFF]/g, '')
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '')
    .replace(/\r\n?/g, '\n')
    .trim()
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function inlineMarkdown(value: string): string {
  return value
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[(S\d+)\]/g, '<span class="answer-citation">[$1]</span>')
}

function renderAssistantText(value: string): string {
  const safe = escapeHtml(cleanPlainText(value))
  const lines = safe.split('\n')
  const html: string[] = []
  let inList = false
  let listType: 'ul' | 'ol' = 'ul'

  const closeList = () => {
    if (!inList) return
    html.push(`</${listType}>`)
    inList = false
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      closeList()
      continue
    }

    const heading = line.match(/^#{1,4}\s+(.+)$/)
    if (heading) {
      closeList()
      html.push(`<div class="answer-heading">${inlineMarkdown(heading[1])}</div>`)
      continue
    }

    const bullet = line.match(/^[-*•]\s+(.+)$/)
    if (bullet) {
      if (!inList || listType !== 'ul') {
        closeList()
        html.push('<ul>')
        inList = true
        listType = 'ul'
      }
      html.push(`<li>${inlineMarkdown(bullet[1])}</li>`)
      continue
    }

    const ordered = line.match(/^\d+[.、]\s*(.+)$/)
    if (ordered) {
      if (!inList || listType !== 'ol') {
        closeList()
        html.push('<ol>')
        inList = true
        listType = 'ol'
      }
      html.push(`<li>${inlineMarkdown(ordered[1])}</li>`)
      continue
    }

    closeList()
    html.push(`<p>${inlineMarkdown(line)}</p>`)
  }
  closeList()
  return html.join('')
}
</script>
