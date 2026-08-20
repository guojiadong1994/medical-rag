# Retrieval Recall Diagnosis V1

## 为什么先做这个，而不是直接上 Reranker

当前 Hybrid RRF 的 `no_relevant_in_top_k=2` 表示有两道题的正确证据没有进入 Top-10。
Reranker 只能对已经召回的候选重新排序，不能凭空找回没有进入候选集的证据。因此在进入
Reranker 前，先把“漏召回发生在哪一层”诊断清楚。

## 诊断链

```text
人工证据规则
    ↓
chunks.json 中是否存在正确证据？
    ↓ yes
Dense 全量排名是多少？
BM25 全量排名是多少？
    ↓
当前 candidate_k=30 是否提前截断？
    ↓
RRF 融合后排名是多少？
```

这能区分：

1. `EVIDENCE_MISSING_FROM_CHUNKS`：上游数据/Chunk/标注问题；
2. `FUSION_RANKING_LOSS`：召回没问题，融合排序损失；
3. `FUSION_TOPK_LOSS`：已进入融合候选，但最终 Top-K 被挤掉；
4. `CANDIDATE_POOL_BOTTLENECK`：candidate_k 太小；
5. `WEAK_RECALL`：Dense 与 BM25 本身都把正确证据排得靠后。

## 运行

```bash
python scripts/diagnose_retrieval_recall.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10 \
  --candidate-k 30 \
  --deep-k 0 \
  --tag hybrid_v1
```

`--deep-k 0` 表示诊断时临时搜索全部 Chunk。它不是生产参数，只用于定位问题。

输出：

```text
data/processed/hypertension_2024/evaluation/
├── retrieval_recall_diagnosis_hybrid_v1.json
└── retrieval_recall_diagnosis_hybrid_v1.md
```

## 学习重点

### Recall 和 Rerank 的职责不同

- Retriever 的目标：尽量把正确证据送进候选池（Recall）。
- Reranker 的目标：在候选池中把正确证据排得更靠前（Precision / ranking）。

如果正确证据连 Top-30 候选池都没进入，换再强的 Reranker 也救不回来。

### candidate_k 与 top_k 不同

`candidate_k=30` 表示 Dense/BM25 各先取约 30 个候选参与 RRF；`top_k=10` 表示融合后最终只保留前 10。
如果正确证据在 Dense 第 40、BM25 第 50，那么当前 RRF 根本看不到它；这叫候选池截断。

## 面试对应

这一步对应 RAG 检索面试里常见的：

- “召回率低怎么排查？”
- “Reranker 能解决所有检索问题吗？”
- “Top-K 和候选集大小怎么设置？”
- “BM25 + Dense 多路召回后怎么定位是哪一路出了问题？”

工程回答不应只说“换 Embedding 模型”，而应逐层检查：数据/Chunk → Query → Retriever → Fusion → Reranker。
