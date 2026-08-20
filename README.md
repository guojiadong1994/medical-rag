# Medical RAG V1.1 · 智护医疗完整项目

这是 **JD 特定人群生理孪生与医疗保障大模型平台**中的医疗知识增强检索子系统。

V1.1 在已经完成的真实 RAG（检索增强生成）问答链路基础上，重点把项目从“实验脚本”推进成“产品流程”：**知识库新增资料开始自动入库，AI 健康助手增加成熟的等待反馈和证据展示。**

## 当前完整产品包含

- `apps/web/`：原有“智护医疗”完整网页前端；
- `src/medical_rag/`：真实医疗知识库问答后端；
- `scripts/`：解析、检索、评测与运维脚本；
- `doc/`：开发、评测和架构文档；
- `tests/`：自动测试；
- `deployment/`、`migrations/`：原有部署与数据库目录。

## 问答主链

```text
问题
→ BGE-M3 语义向量检索 + BM25 关键词检索
→ RRF（倒数排名融合）
→ Reranker（重排序模型）
→ 证据上下文
→ 大模型回答
→ 引用与证据检查
```

## V1.1 新增：自动知识入库

管理员在“医疗知识库”页面上传 PDF 后，不再需要手动运行解析、分块和向量化命令：

```text
上传 PDF
→ 后台处理任务
→ PDF 解析与清洗
→ 结构感知知识分块
→ BGE-M3 语义向量生成
→ 自动加入可检索知识库
```

每份新增文档独立保存在：

```text
data/processed/knowledge_documents/<document_id>/
```

已有的《中国高血压防治指南（2024年修订版）》旧知识制品仍然直接兼容，不需要为了升级 V1.1 重新处理。

## V1.1 新增：更成熟的问答页面

- 发送消息后立即显示“正在分析问题”；
- 随等待时间显示“正在检索知识库”“正在核对证据并组织回答”；
- 展示等待秒数；
- 清理不可见异常字符；
- 安全渲染常见大模型排版；
- 直接展示真正被回答引用的证据；
- 其他检索证据默认折叠；
- 来源卡片展示文件、页码、章节和证据摘要。

## 本地检索默认配置

V1.1 本地默认：

```text
RAG_DENSE_BACKEND=local
```

`local（本地精确向量检索）`：直接使用 NumPy 对向量做精确相似度计算。当前知识库规模较小，结果稳定且足够快。

Milvus（向量数据库）代码仍完整保留，服务器/Linux 环境可以切换：

```text
RAG_DENSE_BACKEND=milvus
```

## 安全更新到你已有项目

**不要删除你当前的 medical-rag 项目。** 你的 `.env`、`.git/` 和 `data/` 是本机运行数据，源码包不会携带这些真实数据。

解压本包后，在解压目录执行：

```bash
bash SAFE_UPDATE_EXISTING_PROJECT.sh "/你的/medical-rag/路径"
```

该脚本只更新代码，不删除或覆盖：

```text
.env
.git/
data/
```

## 验证与启动

后端：

```bash
conda activate medical
pip install -e ".[product,dev]"
pytest -q
python scripts/preflight_v1.py
python run.py
```

前端另开终端：

```bash
cd apps/web
npm install
npm run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

更详细的企业知识入库流程说明见：

```text
doc/AUTO_INGESTION_AND_ENTERPRISE_FLOW_V1_1.md
```
