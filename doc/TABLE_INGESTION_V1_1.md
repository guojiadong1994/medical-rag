# Table Ingestion V1.1 — 表格召回缺失根因修复

## 1. 背景

固定检索评测中，`grade1_bp` 与 `grade2_bp` 被诊断为 `EVIDENCE_MISSING_FROM_CHUNKS`。人工检查后发现，表6其实已经进入 `chunks.json`，但存在两个数据入库问题：

1. 表6错误继承了上一栏的 `4.4.4 眼底` section；
2. borderless table 的虚拟列切分把数值（例如 `100~109`）拆坏，同时把另一栏正文混入表格。

因此问题不在 BGE-M3、BM25、RRF 或 Reranker，而在 Retrieval 之前的 ingestion 层。

## 2. 本版方法

### 2.1 Caption-column clipping

旧逻辑在发现 `表6 ...` 后，会对标题下方的整页宽度执行 `page.find_tables(strategy="text")`。双栏期刊中，另一栏正文与表格处于同一纵向范围，因此会被误识别为表格单元格。

新逻辑：

- 判断 caption 位于左栏 / 右栏 / 跨栏；
- 只有检测到同一纵向区域确实存在另一栏文本时，才把 `strategy="text"` 的扫描区域限制在 caption 所在列；
- 对真正跨栏表格仍保留整页宽度。

目的：降低 cross-column contamination（跨栏污染）。

### 2.2 Caption bbox as reading-order anchor

`find_tables()` 返回的虚拟 table bbox 可能被污染，不能稳定代表表格真正的阅读位置。

新 `TableBlock` 保留：

- `bbox`：检测到的表格区域；
- `caption_bbox`：表题实际位置。

Chunking 时优先使用 `caption_bbox`，并且只和同栏 TextBlock 比较阅读顺序。因此右栏的表6会在右栏 `4.5.1` 标题之后进入状态机，而不是错误继承左栏 `4.4.4`。

### 2.3 Structured rows + raw-text fallback 双表示

表格仍保留结构化：

- `headers`
- `rows`
- `markdown`

同时新增 `raw_text`：直接根据 PDF 单词坐标，在表格区域按视觉行恢复文字。

最终 `search_text` 同时包含：

1. 结构化行列语义；
2. 必要时的原始表格文本 fallback。

这样即使虚拟列边界把一个数值拆成多个 cell，只要 PDF 文本层本身仍有正确 token（例如 `100~109`），检索语料中仍可保留该精确值。

这不是用规则硬编码 `100~109`，而是保留第二条通用证据通道。

## 3. 新增可观测性

`parse_pdf.py` 现在额外输出：

- `table_strategy_counts`
- `column_clipped_table_count`
- `raw_text_fallback_table_count`
- `table_quality_report.json`

`tables_preview.md` 会展示：

- extraction strategy
- quality flags
- bbox / caption_bbox
- structured table
- raw text fallback
- final search text

## 4. 验证顺序

由于 Parser 改了，必须从 PDF 重新跑完整离线链路：

```bash
python scripts/parse_pdf.py \
  "data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf" \
  --output-dir data/processed/hypertension_2024

python scripts/chunk_document.py \
  data/processed/hypertension_2024/cleaned_document.json

python scripts/embed_chunks.py \
  data/processed/hypertension_2024/chunks.json

python scripts/evaluate_retrieval_methods.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10

python scripts/diagnose_retrieval_recall.py \
  data/processed/hypertension_2024/chunks.json \
  --eval-file doc/evaluation/hypertension_2024_dense_eval_seed.json \
  --top-k 10 \
  --candidate-k 30 \
  --deep-k 0 \
  --tag table_ingestion_v1_1
```

优先人工检查：

```bash
code data/processed/hypertension_2024/tables_preview.md
```

搜索 `表6`，重点确认：

- 不再混入 `眼底` 正文；
- raw text 中存在 `1级高血压 ... 140~159 ... 90~99`；
- raw text 中存在 `2级高血压 ... 160~179 ... 100~109`；
- Chunk 中表6的 section 是 `4.5.1 按血压水平分类和分级`。

## 5. 面试知识点

### RAG 召回低怎么排查？

不要直接换 Embedding 模型。按链路检查：

`原始文档 → Parsing → Cleaning → Chunk Corpus → Retriever → Fusion → Reranker`

如果 ground-truth evidence 在 Chunk Corpus 中已经损坏或 metadata 错误，后面的 Retriever / Reranker 没有办法恢复原始事实。

### 为什么复杂 PDF 不能只 PDF-to-text？

因为文本内容、二维表格结构、版面阅读顺序和 metadata 都可能影响最终检索。尤其双栏 PDF 中，纯坐标扫描容易产生跨栏污染。

### 为什么表格保存两种表示？

结构化表示适合保持行列关系；raw layout text 适合作为保真 fallback，防止 cell segmentation 破坏数字、单位和缩写。两者共同用于 retrieval-friendly representation。

### 这个案例怎么讲？

一次检索评测中，1级、2级高血压问题在 Dense/BM25/Hybrid Top-10 都缺失。Error Analysis 证明不是 Retriever 问题，而是表6在双栏 PDF 解析时发生跨栏污染，且 Table Chunk 错绑到上一章节。通过 caption-column clipping、caption-anchor reading order 和 structured+raw dual representation 修复 ingestion，再重新跑固定测试集验证 Recall 是否恢复。
