# Context Builder V1 Changelog

- 新增 `medical_rag.rag.context`：Citation、ContextSource、RAGContext、ContextBuilder。
- 新增固定 `[S1]...[Sn]` 引用编号与完整来源 metadata。
- 新增 6000 字符默认 Context Budget 与显式截断记录。
- 新增保守 exact-text deduplication。
- 新增 `medical_rag.rag.prompt`：grounded medical prompt builder。
- 新增 Citation ID 语法校验，阻止答案引用不存在的 Source ID。
- 新增 `scripts/build_rag_context.py`，输出 JSON、Markdown Context 和 Prompt Preview。
- 新增 5 个 Context Builder 单元测试。
- 不改变 Parse、Chunk、Embedding、Dense、BM25、RRF、Reranker、Milvus 数据与指标。
