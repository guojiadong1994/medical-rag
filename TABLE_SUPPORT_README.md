# Medical RAG 表格解析补丁

这次只补 **Table Parsing**，不处理图片/VLM。

## 替换文件

将压缩包中的以下文件覆盖到项目根目录对应位置：

- `pyproject.toml`
- `scripts/parse_pdf.py`
- `src/medical_rag/parsing/models.py`
- `src/medical_rag/parsing/pdf_parser.py`
- `src/medical_rag/parsing/__init__.py`
- `src/medical_rag/cleaning/document_cleaner.py`

## 安装依赖

项目根目录执行：

```bash
pip install -e ".[dev]"
```

如果只想补 PyMuPDF：

```bash
pip install "pymupdf>=1.26,<2.0"
```

## 重新解析

```bash
python scripts/parse_pdf.py \
  "data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf" \
  --output-dir data/processed/hypertension_2024
```

## 新增输出

- `tables.json`：结构化表格数据
- `tables_preview.md`：人眼检查用 Markdown 表格
- `parse_report.json`：新增 `table_count`、`table_pages`、`table_text_blocks_separated` 等统计

重点打开：

```bash
code data/processed/hypertension_2024/tables_preview.md
```

搜索：

```text
表6 基于诊室血压的血压分类和高血压分级
```

理想情况下应恢复为 `分类 / 收缩压 / 舒张压` 三列，而不是之前的一整串扁平文本。

## 当前策略

1. 优先使用 PyMuPDF `Page.find_tables(strategy="lines_strict")` 识别有边框/线条的表格。
2. 对 `表6` 这类明确表题，如果第一遍没找到，则只在表题下方的局部区域使用 `strategy="text"`，支持无边框表格。
3. 检测出的表格正文从普通 `TextBlock` 流中剥离，避免正文与表格重复。
4. 每个表格保存 `title / headers / rows / bbox / markdown / search_text`，为后续 Chunking 和 Embedding 做准备。

这仍然是确定性表格解析，不使用大模型。复杂合并单元格、跨页表格后续再单独补。
