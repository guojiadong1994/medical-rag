# 完整目录替换说明

这不是局部 patch。

请将本目录中的 `src/`、`scripts/` 和 `pyproject.toml` 直接替换到 `medical-rag` 项目根目录。

替换后建议执行：

```bash
pip install -e ".[dev]"
python -c "from medical_rag.chunking import StructureAwareChunker; print('chunking imports ok')"
```

然后运行：

```bash
python scripts/chunk_document.py data/processed/hypertension_2024/cleaned_document.json
```
