# Medical RAG — Answer Grounding & Generation Evaluation V1 完整替换包

本包以 **LLM Generation V1 完整包**为基线继续开发，保留此前 `src/`、`scripts/`、`doc/`、`tests/`、`pyproject.toml` 的全部文件。

## 替换方式

将本包中的以下目录/文件整体覆盖到项目根目录：

```text
src/
scripts/
doc/
tests/
pyproject.toml
```

不要删除/覆盖你项目中的：

```text
data/
.env
.git/
```

## 本阶段新增

- Claim → cited evidence 语义支持判断
- expected_facts 覆盖率
- answer correctness
- faithfulness score
- fully grounded rate
- strict overall pass
- 单题已有生成结果审计
- 14 道端到端 Generation Evaluation
- 每题 checkpoint，避免 API 中途失败导致结果全部丢失

## 第一步：测试

```bash
pytest -q
```

## 第二步：先审计你刚才已经生成成功的 2 级高血压答案

```bash
python scripts/judge_rag_answer.py \
  data/processed/hypertension_2024/rag/rag_generation_v1.json \
  --case-id grade2_bp
```

如果没有单独配置 Judge，程序会回退使用你现有的 `MEDICAL_RAG_LLM_*`。

## 第三步：跑完整 14 道端到端评测

```bash
python scripts/evaluate_generation_e2e.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_retrieval_eval_v2.json \
  --context-top-k 5 \
  --max-context-chars 6000 \
  --candidate-k 50 \
  --rerank-k 20
```

输出：

```text
data/processed/hypertension_2024/evaluation/
├── generation_e2e_checkpoint_v1.json
├── generation_e2e_eval_v1.json
└── generation_e2e_eval_v1.md
```

详细原理见：`doc/ANSWER_GROUNDING_EVAL_V1.md`。
