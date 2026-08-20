# medical-rag · Milvus V1 完整替换包

这一版基于 Evaluation V2 完整工作包继续开发，保留现有 `src/`、`scripts/`、`doc/`、`tests/`、`pyproject.toml` 全部内容，并新增 Milvus V1。

## 替换方式

整体覆盖项目对应内容：

```text
src/
scripts/
doc/
tests/
pyproject.toml
```

不要删除项目自己的：

```text
data/
.env
.git/
```

## 已验证

```text
23 passed
```

## 安装

```bash
pip install -e ".[dev,embedding,reranker,milvus]"
```

## 第一步：写入 Milvus Lite

```bash
python scripts/ingest_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --uri data/milvus/medical_rag.db \
  --collection medical_rag_chunks_v1
```

这一步直接复用当前 `embeddings.npy`，不用重新 Parse / Chunk / Embedding。

## 第二步：Milvus Dense Search

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 5 \
  --uri data/milvus/medical_rag.db
```

## 第三步：验证 Metadata Filter

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "高血压分级" \
  --content-type table \
  --top-k 5
```

## 第四步：与 Local Dense 对比

```bash
python scripts/compare_dense_backends.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 10 \
  --uri data/milvus/medical_rag.db
```

重点看：

```text
overlap_ratio
same_rank_ratio
first_rank_mismatch
```

详细原理：

```text
doc/MILVUS_V1.md
doc/MILVUS_V1_CHANGELOG.md
```

## 数据安全

默认 ingestion 只执行 `upsert`，不会删除 Collection。

只有显式加入：

```text
--recreate
```

才会 drop Collection。日常运行不要使用该参数。
