# Reranker V1

## 1. 本阶段目标

当前同一份 14 题种子评测中，`candidate_k=50` 已能让 Hybrid RRF 的 Top-10 覆盖 14/14 条正确证据。下一步不再继续扩大召回池，而是增加第二阶段精排，让已经召回的正确证据尽量前移。

本版固定第一阶段：

- Dense: `BAAI/bge-m3`
- Sparse: 医疗中文 BM25
- Fusion: RRF
- `candidate_k=50`

新增第二阶段：

- Reranker: `BAAI/bge-reranker-base`
- `rerank_k=20`
- 最终评测 `top_k=10`

## 2. 两阶段检索

```text
Query
  ├─ Dense Top50
  └─ BM25 Top50
          ↓
         RRF
          ↓
      RRF Top20
          ↓
Cross-Encoder Reranker
          ↓
      Final Top10
```

Retriever 解决“别漏”，Reranker 解决“排对”。

## 3. 为什么 Reranker 与 Embedding 不一样

Embedding / bi-encoder 会分别编码 Query 与 Chunk，再通过向量相似度快速比较；适合大规模召回。

Reranker 会把 `Query + Candidate Passage` 成对输入同一个序列分类模型，直接输出相关性 logit。因为模型在一次前向中同时看到问题和候选文本，可以利用更细粒度的 token 交互，因此更适合少量候选的精排，但计算成本更高。

## 4. 为什么默认只重排 Top20

当前 Top10 已做到 14/14 覆盖，因此 RRF Top20 足以覆盖现有种子集中的正确证据，并给 Reranker 留出一定纠错空间。先从 20 开始可以控制本地推理成本；后续扩充评测集后再 A/B 测试 10/20/30/50。

## 5. Passage 构造

Reranker 输入不是只给纯正文，而是：

```text
章节：<section>

表格：<table title>   # 表格时存在

<chunk text>
```

这样可以在不引入过长错误 section_path 的情况下，为精排提供必要的局部结构上下文。

## 6. 分数说明

本版保存的是 reranker 的原始 sequence-classification logit，只用于同一 Query 下候选之间的排序，不把它解释为概率。

输出同时保留：

- `reranker_score`
- `pre_rerank_rank`
- `rrf_score`
- `dense_rank`
- `bm25_rank`

因此可以直接观察某个 Chunk 是被 Reranker 提升还是打压。

## 7. 安装

```bash
pip install -e ".[dev,embedding,reranker]"
```

## 8. 评测

无需重新 Parse / Chunk / Embed。直接在当前向量和 Chunk 上执行：

```bash
python scripts/evaluate_reranker.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10 \
  --candidate-k 50 \
  --rerank-k 20 \
  --tag bge_reranker_base_v1
```

输出：

```text
data/processed/hypertension_2024/evaluation/
  reranker_comparison_bge_reranker_base_v1.json
  reranker_comparison_bge_reranker_base_v1.md
```

重点观察：

1. Recall@1 是否提升；
2. MRR 是否提升；
3. Recall@5 / Top10 coverage 是否不能被破坏；
4. 每道题的 `Before -> After` rank movement。

## 9. 单问题检索

```bash
python scripts/search_hybrid_rerank_local.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的舒张压范围是多少？" \
  --candidate-k 50 \
  --rerank-k 20 \
  --top-k 5
```

## 10. 当前验收标准

Reranker V1 不以“用了模型”为成功标准，而以固定评测集上的 A/B 结果为准：

- 如果 MRR / Recall@1 提升，且 Recall@5/Top10 不下降：进入下一步；
- 如果前排提升但有原本 Top10 的正确证据被打掉：分析 rerank_k、passage 构造和具体退化 Query；
- 如果整体下降：保留 Hybrid RRF baseline，不强行上线 Reranker，并做逐 Query Error Analysis。
