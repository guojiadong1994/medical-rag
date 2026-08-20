# Scripts

当前可直接运行的离线脚本：

- `parse_pdf.py`：PDF 文本/表格解析与清洗。
- `chunk_document.py`：结构感知 Chunking。
- `embed_chunks.py`：为 `chunks.json` 生成归一化 Dense Embedding。
- `search_dense_local.py`：在接入 Milvus 前，用 NumPy 做本地 Top-K Dense Retrieval 验证。

更详细的阶段说明统一放在项目根目录 `doc/`。
