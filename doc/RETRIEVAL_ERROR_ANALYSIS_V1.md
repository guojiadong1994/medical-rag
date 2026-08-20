# Retrieval Error Analysis V1

本阶段目的：不要只看 Recall/MRR 总指标，而是定位“哪一道题为什么掉了”。

## 新增能力

### 1. 评测结果支持实验标签

```bash
python scripts/evaluate_dense_retrieval.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10 \
  --tag v1_1
```

会生成：

- `dense_retrieval_eval_report_v1_1.json`
- `dense_retrieval_eval_report_v1_1.md`

避免每次评测覆盖上一版结果。

### 2. 错误分析

```bash
python scripts/analyze_retrieval_errors.py \
  data/processed/hypertension_2024/evaluation/dense_retrieval_eval_report_v1_2.json \
  --baseline data/processed/hypertension_2024/evaluation/dense_retrieval_eval_report_v1_1.json \
  --tag v1_2_vs_v1_1
```

会输出：

- 每道题正确证据首次出现的 rank
- Top-1 与首个正确证据的 score gap
- `MISS_TOP_K` / `NEAR_TIE_RANKING` / `RANKING_GAP` 等分类
- Top-5 的章节、页码、类型与文本预览
- 相比 baseline 哪些题 improved / regressed / unchanged

## 推荐实验顺序

1. 替换 V1.2 代码后，**先不要重新 Chunk**。
2. 用旧的 V1.1 `chunks.json + embeddings.npy` 跑一次 `--tag v1_1`，先把 baseline 保存下来。
3. 再运行 Chunking V1.2。
4. 重新运行 Embedding（Chunk 发生变化后必须重新向量化）。
5. 跑 `--tag v1_2`。
6. 使用 `analyze_retrieval_errors.py --baseline ...` 做逐题比较。

这样可以明确判断 V1.2 到底是真的提升，还是只让文本“看起来更规整”。
