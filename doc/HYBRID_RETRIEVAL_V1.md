# Hybrid Retrieval V1：Stable Chunking + BM25 + Dense + RRF

## 为什么改

此前 Chunking V1.2 虽然结构更整洁，但在固定 14 题检索集上：

- Recall@1：0.4286 → 0.4286
- Recall@3：0.7857 → 0.7143
- Recall@5：0.8571 → 0.7857
- MRR：0.6095 → 0.5893

说明“把短 Chunk 合并得更完整”并没有提高 Dense Retrieval，反而可能造成语义稀释。

因此本版采用两条策略：

1. Chunking 回到更细粒度的 V1.1 风格，仅保留 V1.2 的安全修复；
2. 不再只靠 Dense Embedding，增加 BM25 稀疏检索，并用 RRF 做多路召回融合。

---

## 1. Stable Chunking

保留：

- Section / Paragraph / Sentence 优先切分；
- 800 字为软目标，1200 字为 Narrative 硬上限；
- 完整句子 overlap；
- Table 独立 Chunk；
- 更严格的 Section Detector，降低“95 定义为高血压...”之类假标题。

回退：

- 不再因为 Chunk 小于 180 字就积极与相邻 Chunk 合并。

原因：短医学陈述可能语义非常集中。强行合并会把多个知识点混成一个向量，导致 Dense Embedding 的表示被稀释。

仅删除极窄的版面噪声：`表 / 图 / 注 / 页 / 空白`。

---

## 2. BM25 是什么

BM25 是经典稀疏关键词检索。它不把文本变成神经网络向量，而是利用：

- Query 词是否出现在文档中；
- 词频 TF；
- 逆文档频率 IDF；
- 文档长度归一化。

本项目的 BM25 适配了中文医学文本：

- 中文使用 2-gram / 3-gram 字符特征；
- 保留 `CKD`、`UACR` 等英文缩写；
- 保留 `135/85`、`100~109`、`140/90` 等数值表达；
- 将“二级”规范成“2级”等常见写法。

这样 BM25 更擅长医学缩写、数字阈值、药名、专有名词和精确表达。

---

## 3. Dense 和 BM25 为什么互补

Dense Retrieval（BGE-M3）：

- 擅长语义、同义改写；
- “二级高血压”与“2级高血压”即使字面不同也可能靠近；
- 但对精确数字、缩写、人群边界可能出现语义竞争。

BM25：

- 擅长关键词、数字、缩写、精确术语；
- 但不真正理解语义，同义改写能力弱。

因此两路并行召回通常比单路更稳。

---

## 4. 为什么用 RRF，而不是直接 Dense score + BM25 score

Dense cosine score 例如：`0.73`；BM25 score 可能是：`12.8`。

两种分数没有统一尺度，直接相加没有明确意义。

RRF（Reciprocal Rank Fusion）只看排名：

`RRF(d) = Σ weight_m / (k + rank_m(d))`

默认：

- `k = 60`
- Dense weight = 1
- BM25 weight = 1

如果同一个 Chunk 同时被 Dense 和 BM25 排得很靠前，它会获得两路加分，从而自然提升。

---

## 5. 本版评测方式

使用同一份 `hypertension_2024_dense_eval_seed.json`，同时评测：

1. Dense only
2. BM25 only
3. Dense + BM25 + RRF

统一输出：

- Recall@1
- Recall@3
- Recall@5
- MRR
- Top-K MISS

这样可以判断 Hybrid 是否真的优于纯 Dense，而不是凭感觉。

---

## 6. 运行顺序

Stable Chunking 会改变 chunks，因此必须重新生成 embedding：

```bash
python scripts/chunk_document.py \
  data/processed/hypertension_2024/cleaned_document.json

python scripts/embed_chunks.py \
  data/processed/hypertension_2024/chunks.json
```

统一对比三种检索：

```bash
python scripts/evaluate_retrieval_methods.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10
```

手工看 BM25：

```bash
python scripts/search_bm25_local.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压舒张压范围是多少？" \
  --top-k 5
```

手工看 Hybrid：

```bash
python scripts/search_hybrid_local.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压舒张压范围是多少？" \
  --top-k 5
```

---

## 7. 对应面试知识点

当前实现已经能支持以下问题：

- BM25 与向量检索如何做混合召回与结果融合？
- 多路召回（BM25 + 向量）是怎么融合的？
- 你们 RAG 检索阶段用了什么方法？
- 召回率低怎么系统排查？
- 为什么 RRF 比直接相加 Dense/BM25 原始分数稳定？

回答时应结合本项目实验数据，而不是只背概念。
