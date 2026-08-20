# Chunking V1 本阶段新增/修改

新增：

- `src/medical_rag/chunking/models.py`
- `src/medical_rag/chunking/section_detector.py`
- `src/medical_rag/chunking/chunker.py`
- `scripts/chunk_document.py`
- `CHUNKING_README.md`

修改：

- `src/medical_rag/chunking/__init__.py`
- `src/medical_rag/chunking/README.md`
- `scripts/README.md`

其余 `src/`、`scripts/parse_pdf.py` 等文件完整保留，便于直接覆盖目录，不会因为“补丁包”遗漏旧文件。
