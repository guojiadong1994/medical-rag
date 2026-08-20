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

## V1.1 Runtime Lifecycle Fix (2026-08-20)

### Real runtime evidence

On the user's macOS ARM64 environment:

```text
BGE-M3 + MPS encode alone                         -> OK
Milvus Collection stats (500 rows)                -> OK
Milvus search while Collection is Released        -> normal Python exception
explicit load_collection + Milvus search           -> OK
Milvus load before MPS forward + Milvus search     -> OK
```

The V1 crash therefore was not evidence of corrupt vectors or a broken database.
The observed failure boundary was the native runtime lifecycle around MPS query
execution and a subsequent Milvus load operation.

### Changed

- Added `MilvusDenseIndex.ensure_loaded()`.
- `search()` now guarantees the collection is loaded **before** `encode_query()`.
- Existing `Loaded` state is detected to avoid redundant `load_collection()` calls.
- `search_dense_milvus.py` preloads the collection before its first query forward pass.
- `compare_dense_backends.py` preloads Milvus before Local/Milvus query encoding.
- Added unit tests that assert `load_collection -> encode_query -> search` ordering.

### Data safety

No collection is dropped, recreated, or rewritten by this fix. Existing
`data/milvus/medical_rag.db` can be reused directly; re-ingestion is unnecessary.
