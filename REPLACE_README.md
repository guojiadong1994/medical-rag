# 完整替换包说明

本包基于当前已验证的 Table Retrieval Text V1.2 工作版本继续开发，保留现有 `src/`、`scripts/`、`doc/`、`tests/` 与 `pyproject.toml`，新增 Reranker V1。

建议替换项目中对应目录/文件，不要删除项目根目录中本包未包含的 `data/`、`apps/`、`deployment/`、`.env` 等运行数据和工程文件。

替换后：

```bash
pip install -e ".[dev,embedding,reranker]"
pytest -q
```

当前包单元测试：13 passed。
