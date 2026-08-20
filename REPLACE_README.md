# medical-rag · Evaluation V2 完整替换包

这一版基于上一版 Reranker V1 完整工作包继续开发，保留现有 `src/`、`scripts/`、`doc/`、`tests/` 和 `pyproject.toml`，新增 Evidence-level Multi-positive Evaluation V2。

## 替换方式

用本包中的目录/文件整体覆盖项目对应内容：

```text
src/
scripts/
doc/
tests/
pyproject.toml
```

不要删除项目自己的：

```text
data/
.env
.git/
```

## 先测试

```bash
pip install -e ".[dev,embedding,reranker]"
pytest -q
```

本包已验证：

```text
19 passed
```

## 第一步：只审计标签，不加载模型

```bash
python scripts/audit_eval_labels.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json
```

把终端输出发回，重点看：

```text
zero_match_case_count
```

应为 0。

## 第二步：用 V2 重新评测 Reranker

```bash
python scripts/evaluate_reranker.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json \
  --top-k 10 \
  --candidate-k 50 \
  --rerank-k 20 \
  --tag bge_reranker_base_eval_v2
```

不需要重新 Parse、Chunk、Embedding。

## V1 仍然保留

历史文件：

```text
doc/evaluation/hypertension_2024_dense_eval_seed.json
```

不要删除。后续可以明确区分：

- V1：原始窄标签 baseline
- V2：multi-positive evidence-level labels

详细原理见：

```text
doc/RETRIEVAL_EVALUATION_V2.md
doc/RETRIEVAL_EVALUATION_V2_CHANGELOG.md
```
