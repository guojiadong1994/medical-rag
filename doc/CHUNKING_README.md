# Structure-Aware Chunking V1

本替换包以当前 PDF 文本/表格解析版本为基础，新增结构感知 Chunking。

## 直接替换

用户习惯直接覆盖目录，因此本包提供完整的：

- `src/`
- `scripts/`
- `pyproject.toml`

不是局部补丁。

## 运行

如果 PDF 已经解析过，不需要重新解析，直接：

```bash
python scripts/chunk_document.py \
  data/processed/hypertension_2024/cleaned_document.json
```

默认会在同一目录生成：

- `chunks.json`
- `chunks_preview.md`
- `chunk_report.json`

如果希望从 PDF 重新开始：

```bash
python scripts/parse_pdf.py \
  "data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf" \
  --output-dir data/processed/hypertension_2024

python scripts/chunk_document.py \
  data/processed/hypertension_2024/cleaned_document.json
```

## 默认参数

- target_chars = 800
- max_chars = 1200
- min_chars = 180
- overlap_chars = 120

V1 的重点不是追求某个固定字符数，而是优先保护章节、段落、句子和表格的语义完整性。
