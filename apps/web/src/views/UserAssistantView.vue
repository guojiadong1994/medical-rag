<template>
<div class="assistant-layout">
  <aside class="chat-sidebar"><div style="display:flex;align-items:center;gap:10px;margin-bottom:18px"><div class="brand-mark" style="width:38px;height:38px;font-size:16px">AI</div><div><strong style="font-size:14px">AI 健康助手</strong><div class="muted small" style="margin-top:3px">真实医学知识库检索 + 可追溯引用</div></div></div><div class="muted small" style="margin-bottom:10px">你可以这样问</div><button v-for="question in aiQuickQuestions" :key="question" class="quick-question" @click="send(question)">{{question}}</button><el-alert title="健康助手用于医疗信息理解与健康管理辅助，不替代医生诊断与治疗。" type="info" :closable="false" show-icon style="margin-top:18px"/></aside>
  <section class="chat-main"><header class="chat-header"><el-avatar :size="38" style="background:#0f766e">智</el-avatar><div><strong>健康信息智能解读</strong><div class="muted small" style="margin-top:3px">回答来自当前医疗知识库，并显示实际引用的文件、页码与章节</div></div></header>
    <div class="chat-messages" ref="messageContainer"><div class="message assistant"><el-avatar :size="30" style="background:#0f766e">智</el-avatar><div class="message-bubble">你好，我已经接入真实医疗知识库问答流程。你可以询问高血压指南中的诊断阈值、分级、检查项目等内容。</div></div>
      <div v-for="(message,index) in messages" :key="index" class="message" :class="message.role"><el-avatar :size="30" :style="message.role==='assistant'?'background:#0f766e':'background:#617579'">{{message.role==='assistant'?'智':'我'}}</el-avatar><div class="message-bubble"><div style="white-space:pre-line">{{message.content}}</div><div v-if="message.sources?.length" class="citation-box"><strong style="font-size:11px">参考来源</strong><div v-for="source in message.sources" :key="source.citation_id" class="source-detail"><div><strong>{{source.citation_id}}</strong> · {{source.source_file}} · 第{{source.page_start===source.page_end?source.page_start:`${source.page_start}-${source.page_end}`}}页<span v-if="source.section"> · {{source.section}}</span></div><div class="muted" style="margin-top:5px">{{source.used_in_answer?'已被答案引用':'检索补充证据'}}</div></div></div></div></div>
    </div>
    <div class="chat-input"><el-input v-model="input" size="large" placeholder="输入你想了解的医学知识问题" @keyup.enter="submit"/><el-button type="primary" size="large" :loading="thinking" @click="submit">发送</el-button></div>
  </section>
</div>
</template>
<script setup lang="ts">
import {nextTick,onMounted,ref} from 'vue';import {ElMessage} from 'element-plus';import {aiQuickQuestions} from '@/data/health';import {apiFetch} from '@/api/client'
interface Source { citation_id:string;source_file:string;page_start:number;page_end:number;section?:string|null;used_in_answer:boolean }
interface ChatMessage { role:'user'|'assistant';content:string;sources?:Source[] }
interface RagResponse { answer:string;abstained:boolean;sources:Source[];diagnostics:{grounding_status:string;total_tokens?:number|null} }
const input=ref('');const thinking=ref(false);const messages=ref<ChatMessage[]>([]);const messageContainer=ref<HTMLElement|null>(null)
onMounted(()=>{const prefill=sessionStorage.getItem('assistant-prefill');if(prefill){sessionStorage.removeItem('assistant-prefill');void send(prefill)}})
async function send(question:string){if(!question.trim()||thinking.value)return;messages.value.push({role:'user',content:question.trim()});input.value='';thinking.value=true;await nextTick();messageContainer.value?.scrollTo({top:messageContainer.value.scrollHeight,behavior:'smooth'});try{const result=await apiFetch<RagResponse>('/api/v1/me/assistant/chat',{method:'POST',body:JSON.stringify({question:question.trim()})});messages.value.push({role:'assistant',content:result.answer,sources:result.sources})}catch(error){ElMessage.error(error instanceof Error?error.message:'知识库问答失败');messages.value.push({role:'assistant',content:'知识库问答服务暂时不可用，请检查后端服务、模型配置和知识库运行文件。'})}finally{thinking.value=false;await nextTick();messageContainer.value?.scrollTo({top:messageContainer.value.scrollHeight,behavior:'smooth'})}}
function submit(){void send(input.value)}
</script>
