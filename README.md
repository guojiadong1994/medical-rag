# medical-rag

JD 特定人群生理孪生与医疗保障大模型平台中的 **多源图文医疗知识增强检索子系统**。

当前状态：**Phase 0 / 工程骨架初始化**

## 项目目标

后续逐步完成：

- 多源患者纵向健康档案
- PDF / DOCX / XLSX / CSV / JSON 医疗数据处理
- OCT / UBM 等图文混排检查报告解析
- OCR / Table Parsing / Image Extraction / VLM Caption
- Patient Timeline
- Dense + BM25 Hybrid Retrieval
- RRF + Reranker
- Metadata Filtering
- 医学知识库与 Citation
- RAG Evaluation
- Ontology / GraphRAG
- FastAPI / PostgreSQL / Redis / Milvus / MinIO
- Docker 部署与可观测性
- 后续 vLLM 本地模型服务

## 当前目录

```text
medical-rag/
├── src/medical_rag/
├── apps/web/
├── tests/
├── data/
├── deployment/
├── docs/
├── scripts/
├── migrations/
├── pyproject.toml
├── docker-compose.yml
├── Makefile
└── .env.example
```

## 启动 API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn medical_rag.api.app:app --reload --host 0.0.0.0 --port 8000
```

测试：

```bash
curl http://127.0.0.1:8000/health
```

## 启动基础设施

```bash
cp .env.example .env
docker compose up -d
```

Phase 0 先提供 PostgreSQL、Redis、MinIO。
Milvus、Neo4j、vLLM 会在对应阶段正式加入，避免第一版骨架过重。
