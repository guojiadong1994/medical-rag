# RAG-01A / RAG-01B: PDF Parser + Cleaner

本阶段只解决两件事：

1. 从数字版 PDF 提取带页面、坐标、字体信息的文本块，并估计阅读顺序。
2. 清除重复页眉页脚、页码、异常控制字符与换行噪声，同时保留正文和医学证据。

暂不进行 OCR、表格结构化、标题层级识别、Chunk、Embedding 或向量入库。

## 安装

在 `pyproject.toml` 的 dependencies 中加入：

```toml
"PyMuPDF>=1.26,<2.0",
```

然后：

```bash
pip install -e ".[dev]"
```

## 运行

```bash
python scripts/parse_pdf.py \
  "data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf" \
  --output-dir data/processed/hypertension_2024
```

会生成：

- `parsed_document.json`: 原始结构化解析结果
- `cleaned_document.json`: 清洗后的页面/Block
- `cleaned_preview.txt`: 方便人工浏览
- `parse_report.json`: 本次解析质检统计

## 为什么不是直接 extract_text()

RAG 后续需要页码 Citation、标题层级、表格识别和双栏阅读顺序，因此 Parser 必须保留 bbox/page/block，而不能一开始就把 PDF 压成一整段字符串。

## 为什么不默认 OCR

数字版 PDF 优先读取原生文本层。只有文本层字符过少或乱码比例过高的页面才标记到 `ocr_recommended_pages`，后续 OCR 模块只处理这些页面。
