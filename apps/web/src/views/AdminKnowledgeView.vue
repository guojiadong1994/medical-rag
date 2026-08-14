<template>
  <div class="page-grid">
    <section class="grid-4">
      <div class="metric-card">
        <div class="label">知识文档</div>
        <div class="metric-value"><strong>{{ docs.length }}</strong><span>份</span></div>
        <div class="metric-status status-success">全部可用</div>
      </div>
      <div class="metric-card">
        <div class="label">已索引文档</div>
        <div class="metric-value"><strong>{{ indexedCount }}</strong><span>份</span></div>
        <div class="metric-status status-success">检索服务正常</div>
      </div>
      <div class="metric-card">
        <div class="label">知识片段</div>
        <div class="metric-value"><strong>{{ totalChunks }}</strong><span>Chunks</span></div>
        <div class="metric-status status-success">向量索引已建立</div>
      </div>
      <div class="metric-card">
        <div class="label">最近更新</div>
        <div class="metric-value"><strong style="font-size:20px">2026-08-12</strong></div>
        <div class="metric-status status-success">知识库持续维护</div>
      </div>
    </section>

    <section class="panel">
      <div class="section-row">
        <div>
          <h3 class="panel-title">医疗知识库</h3>
          <p class="panel-subtitle">管理用于医学知识检索与 AI 回答引用的权威资料</p>
        </div>
        <el-button type="primary" @click="uploadDialog = true"><Plus style="width:15px;margin-right:6px" />添加医学资料</el-button>
      </div>

      <div style="display:flex;gap:10px;margin-bottom:18px">
        <el-input v-model="keyword" clearable placeholder="搜索文档名称" style="max-width:320px" />
        <el-select v-model="category" style="width:150px">
          <el-option label="全部类型" value="全部" />
          <el-option label="临床指南" value="临床指南" />
          <el-option label="用药参考" value="用药参考" />
        </el-select>
      </div>

      <el-table :data="filteredDocs" border style="width:100%">
        <el-table-column prop="name" label="文档名称" min-width="280" show-overflow-tooltip />
        <el-table-column prop="category" label="类型" width="120" />
        <el-table-column label="处理状态" width="120">
          <template #default="scope"><el-tag :type="scope.row.status === '已索引' ? 'success' : 'warning'">{{ scope.row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="chunks" label="知识片段" width="110" />
        <el-table-column prop="size" label="文件大小" width="100" />
        <el-table-column prop="updatedAt" label="更新时间" width="165" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="scope">
            <el-button text type="primary" @click="detailDoc = scope.row">查看</el-button>
            <el-button text @click="reindex(scope.row)">重新处理</el-button>
            <el-button text type="danger" @click="remove(scope.row)">删除</el-button>
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
          <el-upload drag :auto-upload="false" :limit="1" accept=".pdf" :on-change="handleFileChange">
            <el-icon size="30"><UploadFilled /></el-icon>
            <div style="margin-top:8px">拖拽 PDF 文件到此处，或点击选择文件</div>
            <template #tip><div class="muted small">当前支持 PDF 文档，添加后将自动进行解析、分块与索引处理。</div></template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :disabled="!selectedFileName" @click="addDocument">确认添加</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" size="480px" :title="detailDoc?.name">
      <template v-if="detailDoc">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="文档编号">{{ detailDoc.id }}</el-descriptions-item>
          <el-descriptions-item label="资料类型">{{ detailDoc.category }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ detailDoc.size }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ detailDoc.updatedAt }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin:24px 0 12px">处理流程</h4>
        <el-steps direction="vertical" :active="4" finish-status="success">
          <el-step title="文档解析" description="已完成文本与结构提取" />
          <el-step title="内容分块" :description="`已生成 ${detailDoc.chunks} 个知识片段`" />
          <el-step title="向量化" description="嵌入表示已生成" />
          <el-step title="检索索引" description="当前可用于知识检索" />
        </el-steps>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { Plus, UploadFilled } from '@element-plus/icons-vue'
import { knowledgeDocuments } from '@/data/health'

interface KnowledgeDoc {
  id: string
  name: string
  category: string
  status: string
  chunks: number
  updatedAt: string
  size: string
}

const docs = ref<KnowledgeDoc[]>(knowledgeDocuments.map((item) => ({ ...item })))
const keyword = ref('')
const category = ref('全部')
const uploadDialog = ref(false)
const newCategory = ref('临床指南')
const selectedFileName = ref('')
const detailDoc = ref<KnowledgeDoc | null>(null)
const detailVisible = computed({ get: () => Boolean(detailDoc.value), set: (value) => { if (!value) detailDoc.value = null } })

const filteredDocs = computed(() => docs.value.filter((doc) => {
  const typeOk = category.value === '全部' || doc.category === category.value
  return typeOk && doc.name.toLowerCase().includes(keyword.value.trim().toLowerCase())
}))
const indexedCount = computed(() => docs.value.filter((doc) => doc.status === '已索引').length)
const totalChunks = computed(() => docs.value.reduce((sum, doc) => sum + doc.chunks, 0).toLocaleString())

function handleFileChange(file: UploadFile) {
  selectedFileName.value = file.name
}

function addDocument() {
  docs.value.unshift({
    id: `K${String(Date.now()).slice(-6)}`,
    name: selectedFileName.value,
    category: newCategory.value,
    status: '处理中',
    chunks: 0,
    updatedAt: '2026-08-14 14:38',
    size: '待处理',
  })
  uploadDialog.value = false
  selectedFileName.value = ''
  ElMessage.success('医学资料已添加，正在进行知识处理')
}

function reindex(doc: KnowledgeDoc) {
  doc.status = '处理中'
  ElMessage.success(`已开始重新处理：${doc.name}`)
  window.setTimeout(() => { doc.status = '已索引'; if (!doc.chunks) doc.chunks = 236 }, 900)
}

async function remove(doc: KnowledgeDoc) {
  try {
    await ElMessageBox.confirm(`确认从医疗知识库中删除“${doc.name}”吗？`, '删除确认', { type: 'warning' })
    docs.value = docs.value.filter((item) => item.id !== doc.id)
    ElMessage.success('已删除')
  } catch {
    // 用户取消删除
  }
}
</script>
