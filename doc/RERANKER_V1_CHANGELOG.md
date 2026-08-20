# Reranker V1 Changelog

## 2026-08-20

- 新增 `TextReranker` 抽象接口。
- 新增 `HFSequenceClassificationReranker`，默认 `BAAI/bge-reranker-base`。
- 新增 `HybridRerankerIndex`：RRF Top-N -> Cross-Encoder -> Final Top-K。
- 新增 `hybrid_rerank` SearchHit / SearchResponse，保留 RRF 前排名和 Dense/BM25 诊断信息。
- 新增 `scripts/search_hybrid_rerank_local.py`。
- 新增 `scripts/evaluate_reranker.py`，对比 RRF before/after，并记录逐问题排名移动。
- 将已验证的 Hybrid `candidate_k` 默认值从 30 更新为 50。
- 新增 reranker 可选依赖组。
- 新增 2 个 Reranker 单元测试；当前完整单测 13 passed。
