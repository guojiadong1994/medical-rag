# Embedding V1：Dense Embedding + 本地 Top-K 验证

## 目标

这一阶段只验证两件事：

1. `chunks.json` 能稳定转换成同维度、有限值、L2 归一化的 Dense Embedding。
2. 不接 Milvus，先用 NumPy 点积做 Top-K 检索，确认相关 Chunk 能被召回。

## 默认模型

默认使用 `BAAI/bge-m3`。代码只使用它的 Dense Embedding 能力，后续是否启用 sparse / ColBERT 再单独评估。

当前默认：

- Dense 向量维度：由模型运行时读取（BGE-M3 为 1024）。
- `max_seq_length=2048`：当前 Chunk 最大约 1200 中文字符，先避免无必要的 8192 长上下文计算；命令行可以修改。
- L2 normalize：开启。
- 相似度：归一化向量点积，即 cosine similarity。

## 为什么不直接上 Milvus

先把 Embedding 层单独验证。如果检索错了，可以明确判断是 Chunk / Embedding 的问题，而不是同时混入 Milvus 索引参数、数据库 schema 等变量。

## 输出文件

`embed_chunks.py` 生成：

- `embeddings.npy`：`float32 [N, D]` 矩阵，不把巨大向量写进 JSON。
- `embedding_manifest.json`：模型、维度、Chunk 顺序，以及每个 `embedding_text` 的 SHA-256。
- `embedding_report.json`：NaN/Inf、向量范数、设备、耗时等诊断。

Manifest 中保存文本哈希是为了防止一种常见错误：Chunk 被重新生成后却继续使用旧 Embedding。检索脚本发现 Chunk ID 或 `embedding_text` 已变化时会拒绝运行，要求重新向量化。

## 安装

```bash
pip install -e ".[dev,embedding]"
```

第一次运行默认模型时，需要从 Hugging Face 下载模型文件。

## 生成 Embedding

```bash
python scripts/embed_chunks.py \
  data/processed/hypertension_2024/chunks.json
```

Mac 如果自动设备有兼容问题，可先强制 CPU：

```bash
python scripts/embed_chunks.py \
  data/processed/hypertension_2024/chunks.json \
  --device cpu
```

## 本地 Dense Retrieval 验证

```bash
python scripts/search_dense_local.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的舒张压范围是多少？" \
  --top-k 5
```

建议至少人工检查以下问题：

- `2级高血压的舒张压范围是多少？`
- `家庭血压诊断高血压的标准是多少？`
- `高血压患者需要做哪些实验室检查？`
- `正常高值血压是多少？`

如果相关表格/正文长期进不了 Top-5，先检查 Chunk 与 Embedding，再进入 Milvus。
