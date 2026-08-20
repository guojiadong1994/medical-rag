# medical-rag · Context Builder V1 完整替换包

本包基于 Milvus V1.1 Runtime Fix 完整包继续开发，并保留既有 `src/`、`scripts/`、`doc/`、`tests/` 和 `pyproject.toml`。

## 替换

将本包中的以下内容覆盖到项目根目录：

- `src/`
- `scripts/`
- `doc/`
- `tests/`
- `pyproject.toml`

不要删除或覆盖自己的：

- `data/`
- `.env`
- `.git/`

## 测试

```bash
pytest -q
```

## Context Builder 验收

```bash
python scripts/build_rag_context.py \
  data/processed/hypertension_2024/chunks.json \
  --query "2级高血压的收缩压和舒张压范围是多少？" \
  --context-top-k 5 \
  --max-context-chars 6000
```

输出到：

`data/processed/hypertension_2024/rag/`

- `rag_context_v1.json`
- `rag_context_v1.md`
- `rag_prompt_preview_v1.md`

本阶段不调用 LLM。先验证“正确证据是否以正确来源、正确预算、正确 Citation ID 进入 Prompt”，再进入 LLM Generation V1。
