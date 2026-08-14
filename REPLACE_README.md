# 完整目录替换说明

这不是增量补丁，而是用于**直接替换整个目录**的完整包。

包含：

- `src/`：完整 Python 后端目录（恢复原有后端骨架，并加入 PDF / Cleaning / Table Parsing）
- `scripts/`：完整脚本目录（包含 `parse_pdf.py`）
- `pyproject.toml`：包含 PyMuPDF 依赖

## 替换

在项目根目录，把压缩包中的：

- `src` 替换原来的 `src`
- `scripts` 替换原来的 `scripts`
- `pyproject.toml` 覆盖原文件

然后执行：

```bash
pip install -e ".[dev]"
```

先验证导入：

```bash
python -c "from medical_rag.cleaning import DocumentCleaner; from medical_rag.parsing import PdfParser; print('imports ok')"
```

正常输出：

```text
imports ok
```

再运行：

```bash
python scripts/parse_pdf.py \
  "data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf" \
  --output-dir data/processed/hypertension_2024
```
