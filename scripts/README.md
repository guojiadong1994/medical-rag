# Scripts

## Medical RAG V1.0 成品入口

```bash
python scripts/preflight_v1.py
python scripts/ask_v1.py "2级高血压的收缩压和舒张压范围是多少？"
```

- `preflight_v1.py`：启动前检查配置和运行文件，不调用大模型。
- `ask_v1.py`：直接通过统一 MedicalRAGPipeline（医疗 RAG 完整处理流程）执行一次真实问答。

其余脚本保留用于解析、检索实验和离线评测。

当前可直接运行的离线脚本：

- `parse_pdf.py`：PDF 文本/表格解析与清洗。
- `chunk_document.py`：结构感知 Chunking。
- `embed_chunks.py`：为 `chunks.json` 生成归一化 Dense Embedding。
- `search_dense_local.py`：在接入 Milvus 前，用 NumPy 做本地 Top-K Dense Retrieval 验证。

更详细的阶段说明统一放在项目根目录 `doc/`。

## Reranker V1

```bash
python scripts/evaluate_reranker.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --candidate-k 50 \
  --rerank-k 20 \
  --top-k 10
```

单问题：

```bash
python scripts/search_hybrid_rerank_local.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的舒张压范围是多少？"
```


## Evaluation V2

- `audit_eval_labels.py`: 在不加载 Embedding/Reranker 的情况下，扫描当前 chunks，检查每道评测题有多少个可接受 evidence，以及各 evidence rule 实际匹配到哪些 Chunk。

## Milvus V1

写入当前 Chunk Embedding：

```bash
python scripts/ingest_milvus.py \
  data/processed/hypertension_2024/chunks.json
```

Milvus Dense Search：

```bash
python scripts/search_dense_milvus.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？"
```

Local Dense / Milvus 一致性验证：

```bash
python scripts/compare_dense_backends.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --top-k 10
```

## Context Builder V1

```bash
python scripts/build_rag_context.py data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --context-top-k 5 \
  --max-context-chars 6000
```

## LLM Generation V1

`generate_rag_answer.py` runs the complete stable offline knowledge path:
Dense + BM25 -> RRF -> Cross-Encoder Reranker -> bounded Context -> OpenAI-compatible LLM -> citation validation.

The script reads LLM settings from CLI flags or these environment variables:

- `MEDICAL_RAG_LLM_BASE_URL`
- `MEDICAL_RAG_LLM_MODEL`
- `MEDICAL_RAG_LLM_API_KEY`

The API key is only used in the HTTP Authorization header and is never written to generation artifacts.

## Answer grounding / end-to-end generation evaluation

```bash
python scripts/judge_rag_answer.py \
  data/processed/hypertension_2024/rag/rag_generation_v1.json \
  --case-id grade2_bp

python scripts/evaluate_generation_e2e.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json \
  --context-top-k 5 \
  --max-context-chars 6000 \
  --candidate-k 50 \
  --rerank-k 20
```

## Generation Safety Evaluation V3

```bash
python scripts/audit_generation_eval_v3.py
python scripts/evaluate_generation_safety_v3.py data/processed/hypertension_2024/chunks.json --challenge-only
```

详见 `doc/GENERATION_SAFETY_EVAL_V3.md`。

## Generation Safety Evaluation V3.1

先审计：

```bash
python scripts/audit_generation_eval_v3_1.py
```

已有 V3 结果时，优先零 LLM 调用离线重评分：

```bash
python scripts/rescore_generation_safety_v3_1.py
```

需要完整 live rerun 时：

```bash
python scripts/evaluate_generation_safety_v3_1.py \
  data/processed/hypertension_2024/chunks.json \
  --challenge-only \
  --context-top-k 5 \
  --max-context-chars 6000 \
  --candidate-k 50 \
  --rerank-k 20
```