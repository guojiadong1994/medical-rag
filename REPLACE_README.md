# medical-rag — LLM Generation V1 完整替换包

这是基于 Context Builder V1 的完整替换包，保留已有 `src/`、`scripts/`、`doc/`、`tests/` 和 `pyproject.toml`，并新增 LLM Generation V1。

## 替换

把压缩包中的这些内容整体覆盖项目根目录同名内容：

- `src/`
- `scripts/`
- `doc/`
- `tests/`
- `pyproject.toml`

不要删除或覆盖你的：

- `data/`
- `.env`
- `.git/`

## 测试

```bash
pytest -q
```

## 配置 LLM

```bash
export MEDICAL_RAG_LLM_BASE_URL="<openai-compatible-base-url>/v1"
export MEDICAL_RAG_LLM_MODEL="<model-name>"
export MEDICAL_RAG_LLM_API_KEY="<api-key>"
```

本地无鉴权模型服务可以不设置 `MEDICAL_RAG_LLM_API_KEY`。

## 运行

```bash
python scripts/generate_rag_answer.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --context-top-k 5 \
  --max-context-chars 6000
```

产物位于：

```text
data/processed/hypertension_2024/rag/
  rag_generation_v1.json
  rag_answer_v1.md
  rag_generation_trace_v1.md
```
