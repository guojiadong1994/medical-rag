# Milvus V1：从本地 Dense 检索迁移到向量数据库

## 1. 本阶段目标

当前项目已经完成：

- PDF / Table Parsing
- Structure-aware Chunking
- BGE-M3 Embedding
- Local Dense Retrieval
- BM25
- RRF Hybrid Retrieval
- BGE Reranker
- Evaluation V2

Milvus V1 不继续刷检索指标，而是把当前已经验证过的 Dense Embedding 从 `embeddings.npy` 持久化到真正的向量数据库，并验证：

1. Collection Schema 能正确表达 Chunk + Vector + Metadata。
2. 已有 1024 维 BGE-M3 向量无需重新计算即可写入 Milvus。
3. Milvus Dense Search 能返回与 Local Dense 高度一致的结果。
4. 可以在向量检索时使用 metadata filter，例如只查表格、只查某页。
5. 客户端代码未来可以只改 URI，从 Milvus Lite 切换到 Standalone / Distributed。

## 2. 为什么 V1 先使用 Milvus Lite

当前只有约 500 个 Chunk，本阶段最重要的是学习和验证数据模型、持久化、搜索接口与 metadata filter，而不是做大规模 ANN 压测。

默认 URI：

```text
data/milvus/medical_rag.db
```

这是一个本地持久化的 Milvus Lite 数据库文件。

后续切换到服务器时，核心代码不需要重写，只需把：

```text
data/milvus/medical_rag.db
```

换成类似：

```text
http://localhost:19530
```

## 3. Collection Schema

V1 Collection：

```text
medical_rag_chunks_v1
```

主要字段：

| 字段 | 类型 | 作用 |
|---|---|---|
| `chunk_id` | VARCHAR, Primary Key | 稳定 Chunk 主键 |
| `vector` | FLOAT_VECTOR | BGE-M3 Dense Embedding |
| `document_id` | VARCHAR | 文档 ID |
| `source_file` | VARCHAR | 来源文件 |
| `content_type` | VARCHAR | narrative / table |
| `section` | VARCHAR | 当前章节 |
| `section_path_json` | VARCHAR | 完整章节路径 |
| `page_start` | INT64 | 起始页 |
| `page_end` | INT64 | 结束页 |
| `text` | VARCHAR | LLM / Citation 使用的原始检索文本 |
| `embedding_text` | VARCHAR | 实际生成向量时使用的文本 |
| `table_title` | VARCHAR | 表格标题 |
| `table_no` | INT64 | 表序号；无表格时使用 -1 |
| `metadata_json` | VARCHAR | 其他 metadata |
| `embedding_model` | VARCHAR | 向量模型名 |
| `embedding_normalized` | BOOL | 是否 L2 归一化 |

向量索引：

```text
AUTOINDEX + COSINE
```

当前 BGE-M3 Embedding 已经 L2 normalize，因此 Local Dense 中的 dot-product 与 cosine 排序语义一致。

## 4. 为什么使用 chunk_id 做主键

本项目不使用 Milvus 自增 ID，而直接使用稳定的 `chunk_id`。

好处：

- Chunk 与 Milvus Entity 一一对应。
- 可重复执行 ingestion。
- 使用 `upsert` 时，同一个 Chunk 更新而不是重复插入。
- 后续 Citation / Debug 可以直接追溯原始 Chunk。

## 5. 数据安全策略

V1 默认不会删除 Collection。

正常执行 ingestion：

```text
existing collection -> upsert
```

只有显式传入：

```bash
--recreate
```

程序才会 drop 现有 Collection 并重新创建。

因此日常命令不要带 `--recreate`。

## 6. 安装

```bash
pip install -e ".[dev,embedding,reranker,milvus]"
```

## 7. 第一步：把现有 Embedding 写入 Milvus

不重新跑 Embedding，直接使用当前：

```text
chunks.json
embeddings.npy
embedding_manifest.json
```

命令：

```bash
python scripts/ingest_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --uri data/milvus/medical_rag.db \
  --collection medical_rag_chunks_v1
```

预期：

```text
chunk_count = 500
dimension = 1024
model_name = BAAI/bge-m3
operation = create+upsert   # 首次
```

第二次执行应变成：

```text
operation = upsert
```

这说明 ingestion 是可重复执行的。

## 8. 第二步：Milvus Dense Search

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 5 \
  --uri data/milvus/medical_rag.db
```

这一阶段的 Query 仍然使用 BGE-M3 生成 1024 维向量，但候选搜索不再通过：

```text
NumPy matrix @ query vector
```

而是：

```text
Milvus Collection -> vector search -> Top-K entities
```

## 9. 第三步：Metadata Filter

只搜索表格：

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --content-type table \
  --top-k 5
```

只搜索覆盖 PDF 第 10 页的 Chunk：

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "高血压分级" \
  --page 10 \
  --top-k 5
```

页过滤不是简单的：

```text
page_start == 10
```

而是：

```text
page_start <= 10 AND page_end >= 10
```

因为一个 Chunk 可能跨页。

## 10. 第四步：Local Dense vs Milvus 一致性验证

```bash
python scripts/compare_dense_backends.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 10 \
  --uri data/milvus/medical_rag.db
```

主要指标：

```text
overlap_ratio
same_rank_ratio
first_rank_mismatch
```

### overlap_ratio

Local Dense Top-K 与 Milvus Top-K 有多少相同 Chunk。

例如：

```text
overlap_ratio = 1.0
```

表示 Top10 候选集合完全一致。

### same_rank_ratio

不仅候选相同，而且对应位置也完全相同的比例。

对于完全精确搜索，可以接近 1.0；未来切到 ANN 索引后，即使候选基本一致，也可能出现少量顺序变化。

因此工程迁移时优先确认：

```text
高 overlap
```

然后再检查 ranking 差异是否合理。

## 11. 这一步解决什么，不解决什么

Milvus 主要解决：

- Vector persistence
- Collection / Schema
- Metadata filtering
- 大规模向量检索接口
- 后续 ANN index
- 服务化部署

Milvus 本身不会自动把：

```text
Recall@1 78.6%
```

变成更高。

排序质量仍主要来自：

```text
Embedding
+ BM25
+ RRF
+ Reranker
```

## 12. 面试知识点

### Q1：为什么需要向量数据库？

小数据量时可以直接用 NumPy 暴力计算 cosine similarity，但随着向量数量增长，需要持久化、索引、metadata filter、并发检索和服务化能力，因此需要 Milvus 一类向量数据库。

### Q2：Milvus 和 Embedding Model 是一回事吗？

不是。Embedding Model 负责把文本变成向量；Milvus 负责存储、索引和搜索这些向量。

### Q3：为什么用 COSINE？

当前 BGE-M3 向量经过 L2 normalization，Local Dense 使用 dot product。归一化向量的 dot product 与 cosine similarity 等价，所以 Milvus 使用 COSINE 能与现有本地验证链保持一致的相似度语义。

### Q4：为什么先 Milvus Lite，后 Standalone？

当前语料只有约 500 个 Chunk，V1 的目标是先验证 schema、ingestion、search 和 filter。Milvus Lite 与服务器部署共享 MilvusClient API，后续可通过替换 URI 平滑迁移，而无需现在就引入额外部署复杂度。

### Q5：为什么 ingestion 用 upsert？

因为 `chunk_id` 是稳定主键，重复执行 ingestion 时应该更新相同 Entity，而不是产生重复数据。这样更接近可重复、可恢复的工程数据流水线。

## 12. V1.1：macOS ARM64 + MPS 的 Collection 生命周期修复

真实联调表明，BGE-M3/MPS、Milvus Lite 数据文件、500 条 Entity 和 COSINE
search 各自都正常。原 V1 的 native crash 出现在 Query 已经完成 MPS forward
之后，再去执行 Milvus `load_collection()` 的运行时顺序。

V1.1 统一改为：

```text
BGE-M3 模型初始化
-> MilvusClient
-> get_load_state
-> 必要时 load_collection
-> MPS encode_query
-> Milvus search
```

`ensure_loaded()` 会先读取 load state；已经 Loaded 时不会重复 load。这样既满足
Milvus 的查询生命周期要求，也避免在 MPS forward 之后再触发底层 Collection
加载路径。

注意：这个修复改变的是 **Resource Lifecycle Management**，不是 Embedding、
相似度算法或 Collection 数据，因此无需重新 Parse / Chunk / Embedding / Ingest。
