# Retrieval Evaluation V2 Changelog

## 2026-08-20

### Added

- `doc/evaluation/hypertension_2024_retrieval_eval_v2.json`
  - 14 个原种子 Query 保持不变；
  - 从窄单正例规则升级为 27 条 evidence-level multi-positive rules；
  - 增加 `expected_facts`、`rule_id`、`description`。
- `KeywordProximityRule`
  - 支持关键词在有限字符窗口内共同出现，减少长 Chunk 中的伪关联。
- `table_title_contains_any`
- `excluded_keywords`
- `matched_rule_ids`
  - 每个 Retrieval hit 可以解释自己为什么被判 relevant。
- `scripts/audit_eval_labels.py`
  - 在不加载模型的情况下审计 Ground Truth 与当前 Chunk Corpus。

### Changed

- `RetrievalEvalSuite` 增加 `version` 与 `labeling_policy`。
- `RetrievalEvalCase` 增加 `expected_facts`。
- `RetrievalEvalReport` 增加 `suite_version`。
- `RetrievalEvalCaseResult` 增加 `relevant_hit_count`。
- `evaluate_reranker.py` 报告增加 Evaluation Version 与 first matched rule。

### Compatibility

- V1 `hypertension_2024_dense_eval_seed.json` 保留，不删除、不覆盖。
- V1 Schema 仍可正常加载；新增字段均有默认值。
- 现有 Dense / BM25 / Hybrid / Reranker API 保持兼容。

### Verification

```text
pytest -q
19 passed
```
