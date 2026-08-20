# Retrieval Evaluation V1

本阶段在接入 Milvus 前，先用当前本地 Dense Retrieval 建立可重复的检索基线。

## 目标

- 用人工标注的小型问题集验证正确证据是否进入 Top-K。
- 输出 Recall@1、Recall@3、Recall@5 与 MRR。
- 将排序问题与向量数据库工程问题分离，避免过早接 Milvus 后难以定位问题。

## 运行

```bash
python scripts/evaluate_dense_retrieval.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10
```

输出：

```text
data/processed/hypertension_2024/evaluation/
├── dense_retrieval_eval_report.json
└── dense_retrieval_eval_report.md
```

## 指标

- Recall@1：第一名是否出现合格证据。
- Recall@3：前三名是否至少出现一条合格证据。
- Recall@5：前五名是否至少出现一条合格证据。
- MRR：第一个合格证据排名的倒数均值，越高说明排序越靠前。

当前 seed 只是用于建立基线，不是最终医学评测集。后续应人工核对并持续扩充。
