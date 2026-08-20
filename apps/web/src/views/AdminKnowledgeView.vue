<template>
  <div class="page-grid">
    <section class="grid-4">
      <div class="metric-card">
        <div class="label">知识文档</div>
        <div class="metric-value"><strong>{{ docs.length }}</strong><span>份</span></div>
        <div class="metric-status status-success">统一管理知识来源</div>
      </div>
      <div class="metric-card">
        <div class="label">已索引文档</div>
        <div class="metric-value"><strong>{{ indexedCount }}</strong><span>份</span></div>
        <div class="metric-status status-success">可直接参与问答检索</div>
      </div>
      <div class="metric-card">
        <div class="label">知识片段</div>
        <div class="metric-value"><strong>{{ totalChunks }}</strong><span>片段</span></div>
        <div class="metric-status status-success">来自全部已完成文档</div>
      </div>
      <div class="metric-card">
        <div class="label">后台任务</div>
        <div class="metric-value"><strong>{{ processingCount }}</strong><span>个</span></div>
        <div class="metric-status" :class="processingCount ? 'status-warning' : 'status-success'">
          {{ processingCount ? '知识入库任务正在执行' : '当前无处理中任务' }}
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="section-row">
        <div>
          <h3 class="panel-title">医疗知识库</h3>
          <p class="panel-subtitle">上传资料后自动执行解析、分块、向量化和发布，无需再手动运行脚本</p>
        </div>
        <el-button type="primary" @click="uploadDialog = true">
          <Plus style="width:15px;margin-right:6px" />添加医学资料
        </el-button>
      </div>

      <div class="knowledge-toolbar">
        <el-input v-model="keyword" clearable placeholder="搜索文档名称" class="knowledge-search" />
        <el-select v-model="category" class="knowledge-category">
          <el-option label="全部类型" value="全部" />
          <el-option label="临床指南" value="临床指南" />
          <el-option label="用药参考" value="用药参考" />
          <el-option label="未分类" value="未分类" />
        </el-select>
        <el-button :loading="loading" @click="loadDocuments">刷新</el-button>
      </div>

      <el-table :data="filteredDocs" border style="width:100%" v-loading="loading">
        <el-table-column prop="name" label="文档名称" min-width="260" show-overflow-tooltip />
        <el-table-column prop="category" label="类型" width="110" />
        <el-table-column label="处理状态" min-width="210">
          <template #default="scope">
            <div class="knowledge-status-cell">
              <div class="knowledge-status-row">
                <el-tag :type="statusTag(scope.row.statusCode)">{{ scope.row.status }}</el-tag>
                <span v-if="scope.row.statusCode !== 'ready'" class="muted small">{{ scope.row.progress }}%</span>
              </div>
              <el-progress
                v-if="isProcessing(scope.row.statusCode)"
                :percentage="scope.row.progress"
                :stroke-width="5"
                :show-text="false"
                class="knowledge-progress"
              />
              <div class="muted small knowledge-stage" :title="scope.row.stageMessage">{{ scope.row.stageMessage }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="chunks" label="知识片段" width="100" />
        <el-table-column prop="size" label="文件大小" width="105" />
        <el-table-column prop="updatedAt" label="更新时间" width="165" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="scope">
            <el-button text type="primary" @click="detailDoc = scope.row">查看</el-button>
            <el-button
              v-if="!scope.row.legacy && (scope.row.statusCode === 'failed' || scope.row.statusCode === 'ready')"
              text
              :disabled="reprocessingId === scope.row.id"
              @click="reprocess(scope.row)"
            >
              重新处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="uploadDialog" title="添加医学资料" width="560px">
      <el-alert
        title="上传后将自动进入后台知识入库流程"
        description="系统会依次完成 PDF 解析、文本清洗、知识分块、语义向量生成和检索发布。上传完成后可以关闭窗口，任务会继续处理。"
        type="success"
        :closable="false"
        show-icon
        class="knowledge-upload-alert"
      />
      <el-form label-position="top">
        <el-form-item label="资料类型">
          <el-select v-model="newCategory" style="width:100%">
            <el-option label="临床指南" value="临床指南" />
            <el-option label="用药参考" value="用药参考" />
            <el-option label="未分类" value="未分类" />
          </el-select>
        </el-form-item>
        <el-form-item label="医学资料文件">
          <el-upload
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-icon size="30"><UploadFilled /></el-icon>
            <div style="margin-top:8px">拖拽 PDF 文件到此处，或点击选择文件</div>
            <template #tip>
              <div class="muted small">当前自动入库支持 PDF。上传后不需要再执行解析、分块或向量化命令。</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedFile" :loading="uploading" @click="addDocument">
          上传并自动入库
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="500px" :title="detailDoc?.name">
      <template v-if="detailDoc">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文档编号">{{ detailDoc.id }}</el-descriptions-item>
          <el-descriptions-item label="资料类型">{{ detailDoc.category }}</el-descriptions-item>
          <el-descriptions-item label="处理状态">{{ detailDoc.status }}</el-descriptions-item>
          <el-descriptions-item label="处理进度">{{ detailDoc.progress }}%</el-descriptions-item>
          <el-descriptions-item label="知识片段">{{ detailDoc.chunks }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ detailDoc.size }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ detailDoc.updatedAt }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="detailDoc.error"
          :title="detailDoc.error"
          type="error"
          :closable="false"
          show-icon
          class="knowledge-detail-error"
        />

        <h4 class="knowledge-process-title">自动知识入库流程</h4>
        <el-steps direction="vertical" :active="stepActive(detailDoc.statusCode)" finish-status="success">
          <el-step title="文档接收" description="文件安全保存到知识源目录" />
          <el-step title="解析与清洗" description="读取 PDF 正文、版面和表格并去除噪声" />
          <el-step title="知识分块" description="按章节、段落和表格生成可检索知识片段" />
          <el-step title="语义向量化" description="使用 BGE-M3 将知识片段转换为向量表示" />
          <el-step title="发布到检索库" description="处理完成后自动加入后续问答，无需手动重启" />
        </el-steps>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'
import { apiFetch } from '@/api/client'

interface BackendDocument {
  id: string
  name: string
  category: string
  fileType: string
  sizeText: string
  uploadedAt: string
  updatedAt?: string
  status: string
  statusCode: string
  progress: number
  stageMessage: string
  chunks: number
  error?: string | null
  legacy?: boolean
}

interface KnowledgeDoc {
  id: string
  name: string
  category: string
  status: string
  statusCode: string
  progress: number
  stageMessage: string
  chunks: number
  updatedAt: string
  size: string
  error?: string | null
  legacy: boolean
}

const docs = ref<KnowledgeDoc[]>([])
const keyword = ref('')
const category = ref('全部')
const uploadDialog = ref(false)
const newCategory = ref('临床指南')
const selectedFile = ref<File | null>(null)
const detailDoc = ref<KnowledgeDoc | null>(null)
const loading = ref(false)
const uploading = ref(false)
const reprocessingId = ref('')
let pollTimer: number | undefined

const detailVisible = computed({
  get: () => Boolean(detailDoc.value),
  set: (value) => { if (!value) detailDoc.value = null },
})

const filteredDocs = computed(() => docs.value.filter((doc) => {
  const typeOk = category.value === '全部' || doc.category === category.value
  return typeOk && doc.name.toLowerCase().includes(keyword.value.trim().toLowerCase())
}))
const indexedCount = computed(() => docs.value.filter((doc) => doc.statusCode === 'ready').length)
const processingCount = computed(() => docs.value.filter((doc) => isProcessing(doc.statusCode)).length)
const totalChunks = computed(() => docs.value.reduce((sum, doc) => sum + doc.chunks, 0).toLocaleString())

function mapDocument(item: BackendDocument): KnowledgeDoc {
  return {
    id: item.id,
    name: item.name,
    category: item.category || '未分类',
    status: item.status,
    statusCode: item.statusCode,
    progress: item.progress ?? 0,
    stageMessage: item.stageMessage || '',
    chunks: item.chunks ?? 0,
    updatedAt: item.updatedAt || item.uploadedAt,
    size: item.sizeText,
    error: item.error,
    legacy: Boolean(item.legacy),
  }
}

async function loadDocuments(silent = false) {
  if (!silent) loading.value = true
  try {
    const uploaded = await apiFetch<BackendDocument[]>('/api/v1/knowledge/documents')
    const mapped = uploaded.map(mapDocument)
    docs.value = mapped
    if (detailDoc.value) {
      detailDoc.value = mapped.find((item) => item.id === detailDoc.value?.id) ?? detailDoc.value
    }
    syncPolling()
  } catch (error) {
    if (!silent) ElMessage.warning(error instanceof Error ? error.message : '知识文档列表读取失败')
  } finally {
    if (!silent) loading.value = false
  }
}

function syncPolling() {
  const needsPolling = docs.value.some((item) => isProcessing(item.statusCode))
  if (needsPolling && pollTimer === undefined) {
    pollTimer = window.setInterval(() => { void loadDocuments(true) }, 1800)
  } else if (!needsPolling && pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}

function isProcessing(statusCode: string): boolean {
  return ['uploaded', 'parsing', 'chunking', 'embedding', 'indexing'].includes(statusCode)
}

function statusTag(statusCode: string): 'success' | 'warning' | 'danger' | 'info' {
  if (statusCode === 'ready') return 'success'
  if (statusCode === 'failed') return 'danger'
  if (isProcessing(statusCode)) return 'warning'
  return 'info'
}

function stepActive(statusCode: string): number {
  const mapping: Record<string, number> = {
    uploaded: 1,
    parsing: 2,
    chunking: 3,
    embedding: 4,
    indexing: 5,
    ready: 5,
    failed: 1,
  }
  return mapping[statusCode] ?? 1
}

function handleFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}
function handleFileRemove() {
  selectedFile.value = null
}

async function addDocument() {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const body = new FormData()
    body.append('file', selectedFile.value)
    body.append('category', newCategory.value)
    const created = await apiFetch<BackendDocument>('/api/v1/knowledge/documents', {
      method: 'POST',
      body,
    })
    uploadDialog.value = false
    selectedFile.value = null
    ElMessage.success('资料已上传，后台正在自动完成知识入库')
    await loadDocuments(true)
    detailDoc.value = docs.value.find((item) => item.id === created.id) ?? mapDocument(created)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

async function reprocess(doc: KnowledgeDoc) {
  reprocessingId.value = doc.id
  try {
    await apiFetch(`/api/v1/knowledge/documents/${doc.id}/reprocess`, { method: 'POST' })
    ElMessage.success('已重新提交后台处理任务')
    await loadDocuments(true)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '重新处理失败')
  } finally {
    reprocessingId.value = ''
  }
}

onMounted(() => { void loadDocuments() })
onBeforeUnmount(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
})
</script>
