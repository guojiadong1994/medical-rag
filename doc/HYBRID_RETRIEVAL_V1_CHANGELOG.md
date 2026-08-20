# Hybrid Retrieval V1 Changelog

- Stable Chunking：恢复 V1.1 的细粒度，不再积极合并短 Chunk。
- Stable Chunking：保留 V1.2 的严格 Section 识别。
- Stable Chunking：仅删除明确的单字符版面噪声。
- 新增 `LocalBM25Index`。
- 新增中文医学 BM25 2/3-gram tokenizer。
- 新增 `ReciprocalRankFusionIndex`。
- 新增 Dense / BM25 / Hybrid 三路统一评测。
- 新增 BM25 与 Hybrid 手工检索脚本。
- 无新增第三方 BM25 依赖，BM25 算法在项目内实现，便于学习原理。
