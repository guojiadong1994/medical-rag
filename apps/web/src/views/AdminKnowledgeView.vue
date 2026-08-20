<template>
  <div class="page-grid">
    <section class="grid-4">
      <div class="metric-card">
        <div class="label">知识文档</div>
        <div class="metric-value"><strong>{{ docs.length }}</strong><span>份</span></div>
        <div class="metric-status status-success">知识来源统一管理</div>
      </div>
      <div class="metric-card">
        <div class="label">已索引文档</div>
        <div class="metric-value"><strong>{{ indexedCount }}</strong><span>份</span></div>
        <div class="metric-status status-success">当前检索库可用</div>
      </div>
      <div class="metric-card">
        <div class="label">知识片段</div>
        <div class="metric-value"><strong>{{ totalChunks }}</strong><span>片段</span></div>
        <div class="metric-status status-success">向量索引已建立</div>
      </div>
      <div class="metric-card">
        <div class="label">当前知识库</div>
        <div class="metric-value"><strong style="font-size:20px">高血压指南</strong></div>
        <div class="metric-status status-success">真实问答链路已接通</div>
      </div>
    </section>

    <section class="panel">
      <div class="section-row">
        <div>
          <h3 class="panel-title">医疗知识库</h3>
          <p class="panel-subtitle">保留原有管理界面，并接入真实文档上传与当前知识库状态</p>
        </div>
        <el-button type="primary" @click="uploadDialog = true"><Plus style="width:15px;margin-right:6px" />添加医学资料</el-button>
      </div>

      <div style="display:flex;gap:10px;margin-bottom:18px">
        <el-input v-model="keyword" clearable placeholder="搜索文档名称" style="max-width:320px" />
        <el-select v-model="category" style="width:150px">
          <el-option label="全部类型" value="全部" />
          <el-option label="临床指南" value="临床指南" />
          <el-option label="用药参考" value="用药参考" />
          <el-option label="未分类" value="未分类" />
        </el-select>
        <el-button :loading="loading" @click="loadDocuments">刷新</el-button>
      </div>

      <el-table :data="filteredDocs" border style="width:100%" v-loading="loading">
        <el-table-column prop="name" label="文档名称" min-width="280" show-overflow-tooltip />
        <el-table-column prop="category" label="类型" width="120" />
        <el-table-column label="处理状态" width="120">
          <template #default="scope"><el-tag :type="scope.row.status === '已索引' ? 'success' : 'warning'">{{ scope.row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="chunks" label="知识片段" width="110" />
        <el-table-column prop="size" label="文件大小" width="110" />
        <el-table-column prop="updatedAt" label="更新时间" width="165" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button text type="primary" @click="detailDoc = scope.row">查看</el-button>
            <el-button text @click="showProcessTip(scope.row)">处理说明</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="uploadDialog" title="添加医学资料" width="520px">
      <el-form label-position="top">
        <el-form-item label="资料类型">
          <el-select v-model="newCategory" style="width:100%">
            <el-option label="临床指南" value="临床指南" />
            <el-option label="用药参考" value="用药参考" />
          </el-select>
        </el-form-item>
        <el-form-item label="医学资料文件">
          <el-upload drag :auto-upload="false" :limit="1" accept=".pdf" :on-change="handleFileChange" :on-remove="handleFileRemove">
            <el-icon size="30"><UploadFilled /></el-icon>
            <div style="margin-top:8px">拖拽 PDF 文件到此处，或点击选择文件</div>
            <template #tip><div class="muted small">当前版本支持真实 PDF 上传；上传后进入待处理区，后续由入库流程完成解析、分块、向量化和索引。</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedFile" :loading="uploading" @click="addDocument">确认添加</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="480px" :title="detailDoc?.name">
      <template v-if="detailDoc">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文档编号">{{ detailDoc.id }}</el-descriptions-item>
          <el-descriptions-item label="资料类型">{{ detailDoc.category }}</el-descriptions-item>
          <el-descriptions-item label="处理状态">{{ detailDoc.status }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ detailDoc.size }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ detailDoc.updatedAt }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin:24px 0 12px">处理流程</h4>
        <el-steps direction="vertical" :active="detailDoc.status === '已索引' ? 4 : 1" finish-status="success">
          <el-step title="文档上传" description="文件已进入医疗知识库待处理目录" />
          <el-step title="文档解析与分块" :description="detailDoc.status === '已索引' ? `已生成 ${detailDoc.chunks} 个知识片段` : '等待执行知识入库流程'" />
          <el-step title="向量化" description="将知识片段转换为可检索的向量表示" />
          <el-step title="检索索引" description="建立完成后即可用于医疗知识问答" />
        </el-steps>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'
import { apiFetch } from '@/api/client'

interface KnowledgeDoc {
  id: string
  name: string
  category: string
  status: string
  chunks: number
  updatedAt: string
  size: string
}
interface BackendDocument {
  id: string
  name: string
  category: string
  fileType: string
  sizeText: string
  uploadedAt: string
  status: string
}

const ACTIVE_GUIDE: KnowledgeDoc = {
  id: 'HTN2024',
  name: '中国高血压防治指南（2024年修订版）.pdf',
  category: '临床指南',
  status: '已索引',
  chunks: 500,
  updatedAt: '当前运行知识库',
  size: '本地运行数据',
}

const docs = ref<KnowledgeDoc[]>([ACTIVE_GUIDE])
const keyword = ref('')
const category = ref('全部')
const uploadDialog = ref(false)
const newCategory = ref('临床指南')
const selectedFile = ref<File | null>(null)
const detailDoc = ref<KnowledgeDoc | null>(null)
const loading = ref(false)
const uploading = ref(false)
const detailVisible = computed({ get: () => Boolean(detailDoc.value), set: (value) => { if (!value) detailDoc.value = null } })
const filteredDocs = computed(() => docs.value.filter((doc) => {
  const typeOk = category.value === '全部' || doc.category === category.value
  return typeOk && doc.name.toLowerCase().includes(keyword.value.trim().toLowerCase())
}))
const indexedCount = computed(() => docs.value.filter((doc) => doc.status === '已索引').length)
const totalChunks = computed(() => docs.value.reduce((sum, doc) => sum + doc.chunks, 0).toLocaleString())

async function loadDocuments() {
  loading.value = true
  try {
    const uploaded = await apiFetch<BackendDocument[]>('/api/v1/knowledge/documents')
    const mapped: KnowledgeDoc[] = uploaded
      .filter((item) => !item.name.includes('中国高血压防治指南'))
      .map((item) => ({ id: item.id, name: item.name, category: item.category || '未分类', status: item.status, chunks: 0, updatedAt: item.uploadedAt, size: item.sizeText }))
    docs.value = [ACTIVE_GUIDE, ...mapped]
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '知识文档列表读取失败')
  } finally {
    loading.value = false
  }
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
    await apiFetch<BackendDocument>('/api/v1/knowledge/documents', { method: 'POST', body })
    uploadDialog.value = false
    selectedFile.value = null
    ElMessage.success('医学资料已上传到待处理目录')
    await loadDocuments()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function showProcessTip(doc: KnowledgeDoc) {
  if (doc.status === '已索引') {
    ElMessage.success(`${doc.name} 当前已经进入检索索引`)
  } else {
    ElMessage.info('当前 V1.0 已完成真实上传；新增文档的自动解析与自动重建索引保留为下一阶段能力。')
  }
}

onMounted(() => { void loadDocuments() })
</script>
