# Chunking

当前实现为 Structure-Aware Chunking V1：

- 按章节标题维护 `section` / `section_path`
- 优先按 PDF 清洗后的 block / 段落边界切分
- 超长段落优先按句号、分号等句界切分
- `page` 只作为 metadata，不作为强制 chunk 边界，因此正文允许跨页保持语义连续
- 普通表格单独生成 `table` chunk，不与正文拍平
- 每个 chunk 同时保存 `text` 与带章节上下文的 `embedding_text`

V1 暂不处理图片、复杂跨页表格和语义模型驱动切分。
