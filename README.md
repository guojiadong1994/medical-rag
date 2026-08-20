# medical-rag

JD 特定人群生理孪生与医疗保障大模型平台中的医疗知识增强检索子系统。

当前版本：**Medical RAG V1.0 / 医疗指南单知识库问答成品版**。

## 已完成主链

```text
PDF解析与清洗
→ 表格解析与数值保真
→ Chunk（文本切块）
→ BGE-M3 Embedding（向量表示）
→ Dense Retrieval（向量语义检索）
→ BM25（关键词检索）
→ RRF（倒数排名融合）
→ Reranker（重排序模型）
→ Milvus（向量数据库）
→ Context Builder（证据上下文构建）
→ LLM Generation（大模型生成）
→ Citation（来源引用）
→ Grounding Evaluation（证据绑定评测）
→ Safety Evaluation（安全与拒答评测）
```

## V1.0 快速启动

```bash
pip install -e ".[product,dev]"
cp .env.example .env
python scripts/preflight_v1.py
python run.py
```

浏览器访问：

```text
http://127.0.0.1:8000/rag-demo
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 主要问答接口

```text
POST /api/v1/rag/ask
```

返回最终回答、来源文件、页码、章节、引用状态和各阶段耗时。

## 当前边界

V1.0 先完成“医疗指南单知识库问答成品”。患者时间线、多模态医学图像、知识图谱和大规模多文档自动入库留到后续版本，不在 V1.0 中伪装成已经完成。

更完整说明见：

```text
doc/MEDICAL_RAG_V1_0_PRODUCT.md
```
