# 完整替换包：Generation Safety Evaluation V3

这是基于上一版 `Answer Grounding & End-to-End Generation Evaluation V1` 的完整可替换目录包。

## 替换

将本包中的以下目录/文件整体覆盖到项目根目录：

- `src/`
- `scripts/`
- `doc/`
- `tests/`
- `pyproject.toml`

不要覆盖/删除：

- `data/`
- `.env`
- `.git/`

## 验证

```bash
pytest -q
```

预期：

```text
49 passed
```

先审计 V3：

```bash
python scripts/audit_generation_eval_v3.py
```

然后先只跑 9 条挑战题：

```bash
python scripts/evaluate_generation_safety_v3.py \
  data/processed/hypertension_2024/chunks.json \
  --challenge-only \
  --context-top-k 5 \
  --max-context-chars 6000 \
  --candidate-k 50 \
  --rerank-k 20
```

完整 23 题去掉 `--challenge-only` 即可。

## 本版原则

V3 是“测边界”的版本，不是“继续刷 14 条正例”的版本。先测当前系统在拒答、歧义、表面冲突和具体患者用药请求上的真实 baseline，再决定是否增加 Guardrail。
