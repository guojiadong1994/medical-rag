# Retrieval Recall Diagnosis V1 Changelog

- 新增 `evaluation/diagnostics.py`：深度追踪人工正确证据在 Chunk、Dense、BM25、RRF 各层的排名。
- 新增 `scripts/diagnose_retrieval_recall.py`：自动识别 Top-K 漏召回的根因类别。
- 新增候选池瓶颈诊断：区分 `candidate_k` 截断与 Retriever 本身召回弱。
- 输出 BM25 Query token 与正确证据 token overlap，帮助理解关键词通道为何成功/失败。
- 不改现有 Chunk、Embedding、Dense/BM25/RRF 算法；这一版只增加可解释诊断，避免继续盲调参数。
