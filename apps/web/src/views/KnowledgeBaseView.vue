<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Collection, Document, Refresh, Search, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { fetchKnowledgeDocuments, uploadKnowledgeDocument } from '@/api/knowledge'
import type { KnowledgeDocument } from '@/types'

const loading = ref(false)
const uploading = ref(false)
const keyword = ref('')
const documents = ref<KnowledgeDocument[]>([])
const uploadDialog = ref(false)
const selectedFile = ref<File | null>(null)

const filteredDocuments = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return documents.value
  return documents.value.filter((item) => item.name.toLowerCase().includes(text) || item.category.toLowerCase().includes(text))
})

async function loadDocuments() {
  loading.value = true
  try {
    documents.value = await fetchKnowledgeDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识文档读取失败')
  } finally {
    loading.value = false
  }
}

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

async function submitUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择需要上传的医学文档')
    return
  }
  uploading.value = true
  try {
    await uploadKnowledgeDocument(selectedFile.value)
    ElMessage.success('文档上传成功')
    selectedFile.value = null
    uploadDialog.value = false
    await loadDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '文档上传失败')
  } finally {
    uploading.value = false
  }
}

onMounted(loadDocuments)
</script>

<template>
  <div class="page-container knowledge-page">
    <div class="title-row">
      <div><h1 class="page-title">知识库管理</h1><div class="page-subtitle">统一管理医学指南、专家共识、药品资料及其他专业医学文档。</div></div>
      <el-button type="primary" :icon="UploadFilled" @click="uploadDialog = true">上传知识文档</el-button>
    </div>

    <div class="summary-grid">
      <section class="card summary-card"><div class="icon teal"><el-icon><Collection /></el-icon></div><div><span>文档总数</span><strong>{{ documents.length }}</strong></div></section>
      <section class="card summary-card"><div class="icon blue"><el-icon><Document /></el-icon></div><div><span>已上传文档</span><strong>{{ documents.filter(item => item.status === '已上传').length }}</strong></div></section>
    </div>

    <section class="card document-card">
      <div class="toolbar">
        <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索文档名称或分类" style="width: 360px" />
        <el-button :icon="Refresh" @click="loadDocuments">刷新</el-button>
      </div>
      <el-table v-loading="loading" :data="filteredDocuments" size="large">
        <el-table-column label="文档名称" min-width="300">
          <template #default="{ row }"><div class="document-name"><div><el-icon><Document /></el-icon></div><span>{{ row.name }}</span></div></template>
        </el-table-column>
        <el-table-column prop="category" label="文档分类" width="140" />
        <el-table-column prop="fileType" label="文件类型" width="110" />
        <el-table-column prop="sizeText" label="文件大小" width="110" />
        <el-table-column prop="uploadedAt" label="上传时间" width="170" />
        <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag type="success" effect="light">{{ row.status }}</el-tag></template></el-table-column>
      </el-table>
      <el-empty v-if="!loading && !filteredDocuments.length" description="暂无知识文档" />
    </section>

    <el-dialog v-model="uploadDialog" title="上传医学知识文档" width="520px" :close-on-click-modal="false">
      <div class="upload-note">支持 PDF 文档。上传后的原始文件将进入知识文档目录，后续处理流程可基于同一文档记录继续执行。</div>
      <el-upload drag :auto-upload="false" :limit="1" accept="application/pdf,.pdf" :on-change="handleFileChange">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
        <template #tip><div class="el-upload__tip">单个 PDF 文件</div></template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">确认上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.knowledge-page { padding-top: 24px; }
.title-row { display: flex; justify-content: space-between; align-items: end; margin-bottom: 18px; }
.summary-grid { display: grid; grid-template-columns: repeat(2, 220px); gap: 12px; margin-bottom: 14px; }
.summary-card { min-height: 80px; padding: 14px 16px; display: flex; align-items: center; gap: 12px; }
.summary-card .icon { width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center; font-size: 20px; }
.icon.teal { background: #e8f6f3; color: #0f766e; }
.icon.blue { background: #edf4fa; color: #3a6f98; }
.summary-card > div:last-child { display: flex; flex-direction: column; gap: 3px; }
.summary-card span { color: #8392a1; font-size: 10px; }
.summary-card strong { color: #29465b; font-size: 22px; }
.document-card { overflow: hidden; }
.toolbar { min-height: 68px; padding: 0 18px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e8edf2; }
.document-name { display: flex; align-items: center; gap: 10px; }
.document-name > div { width: 32px; height: 32px; border-radius: 8px; background: #eaf6f4; color: #0f766e; display: grid; place-items: center; }
.document-name span { color: #334e62; font-size: 12px; }
.upload-note { margin-bottom: 16px; color: #65788b; line-height: 1.7; font-size: 12px; }
</style>
