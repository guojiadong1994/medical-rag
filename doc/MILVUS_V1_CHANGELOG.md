# Milvus V1 Changelog

## Added

- `src/medical_rag/retrieval/milvus_dense.py`
  - MilvusClient Dense backend
  - Milvus Lite / remote Milvus 共用 URI 接口
  - custom Collection Schema
  - AUTOINDEX + COSINE
  - idempotent upsert
  - metadata filter builder
  - Local/Milvus ranking comparison
- `scripts/ingest_milvus.py`
- `scripts/search_dense_milvus.py`
- `scripts/compare_dense_backends.py`
- `tests/unit/test_milvus_v1.py`
- `doc/MILVUS_V1.md`

## Changed

- `pyproject.toml`
  - 新增 `milvus` optional dependency：`pymilvus[milvus-lite]`
- `src/medical_rag/retrieval/__init__.py`
  - 导出 Milvus V1 相关接口
- `scripts/README.md`
  - 增加 Milvus V1 命令入口

## Safety

- 默认从不 drop Collection。
- 只有显式 `--recreate` 才允许删除并重建 Collection。
- Ingestion 使用 `upsert`，以 `chunk_id` 为稳定主键。
- 写入前继续复用 `embedding_manifest.json` 校验，防止 stale embedding 与新 chunks 混用。
