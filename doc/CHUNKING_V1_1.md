# Chunking V1.1

本版本只针对当前高血压指南 Chunking V1 暴露出的三个问题做收敛修复，不进入 Embedding。

## 修复 1：PDF 视觉换行恢复

新增 `src/medical_rag/chunking/paragraph_assembler.py`。

解析层继续保留原始 `TextBlock + bbox`，Chunking 前根据阅读顺序、栏位、垂直距离、标题/列表边界，把属于同一段落的视觉行重新拼接。

示例：

- `中国高血压防治指` + `南` -> `中国高血压防治指南`
- `近年来中` + `青年人群` -> `近年来中青年人群`

不直接破坏 cleaned_document.json 的几何结构，避免影响后续表格、图片和版面处理。

## 修复 2：Chunk 边界和 Overlap 不再按字符截断

`target_chars=800` 仍然是软目标，`max_chars=1200` 才是硬上限。

普通切块只在段落/句子等语义边界 flush。Overlap 改为从上一块末尾提取完整句子，不再执行 `text[-120:]` 这种可能从句子中间截断的操作。

只有单个句子本身超过 `max_chars` 时才进入兜底切分，并优先寻找逗号、顿号、冒号或空格附近的安全位置。

## 修复 3：章节识别增强

`SectionDetector` 新增两类能力：

1. 对 `1 我国人群高血压流行及防控现状` 这类短的一级标题，不再强依赖 bold 元数据。
2. 对 `……非随机对照研究1 我国人群高血压流行及防控现状` 这类“上一段文本 + 下一节标题粘连”的 PDF 异常，尝试拆出尾部章节标题。

规则保持保守，短的 `1 推荐类别` 一类表格标签不会因为尾部粘连规则而轻易被识别成章节。

## 重新运行

无需重新解析 PDF，直接对现有 `cleaned_document.json` 重新 Chunk：

```bash
python scripts/chunk_document.py \
  data/processed/hypertension_2024/cleaned_document.json
```

输出仍为：

- `chunks.json`
- `chunks_preview.md`
- `chunk_report.json`

报告新增：

- `sectioned_narrative_count`
- `unsectioned_narrative_count`
- `sectioned_narrative_ratio`
- `short_chunk_count`
- `over_target_chunk_count`
- `over_max_chunk_count`

## 当前暂不处理

- 图片 / 流程图理解
- 极复杂表格、跨页表格
- Embedding / Milvus

这些内容继续后置，先验证 Chunking V1.1 的文本完整性和章节稳定性。
