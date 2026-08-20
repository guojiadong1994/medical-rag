# Milvus V1.1 Runtime Lifecycle Fix · 完整替换包

本包基于 Milvus V1 当前完整版本制作，保留所有既有 `src/`、`scripts/`、`doc/`、
`tests/` 和 `pyproject.toml` 内容，只修复 macOS ARM64 + MPS + Milvus Lite 查询时
的 Collection load 生命周期问题。

## 不要删除

```text
data/
.env
.git/
data/milvus/medical_rag.db
```

已有 500 条 Milvus 数据无需重新 ingest。

## 替换

```text
src/
scripts/
doc/
tests/
pyproject.toml
```

## 验证

```bash
pytest -q
```

然后直接重新运行：

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 5 \
  --uri data/milvus/medical_rag.db
```

再验证 metadata filter：

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --content-type table \
  --top-k 5 \
  --uri data/milvus/medical_rag.db
```

最后做 backend consistency：

```bash
python scripts/compare_dense_backends.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 10 \
  --uri data/milvus/medical_rag.db
```
