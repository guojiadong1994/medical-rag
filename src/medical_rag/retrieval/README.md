# retrieval

当前检索模块包含：

- Local Dense Retrieval：NumPy exact dense baseline。
- Milvus Dense Retrieval：Milvus V1 持久化向量检索与 metadata filter。
- BM25：中文医疗 n-gram sparse retrieval。
- RRF：Dense + BM25 rank fusion。
- Reranker：Hybrid candidates 的 Cross-Encoder 精排。

Milvus V1 详细说明见项目根目录：

```text
doc/MILVUS_V1.md
```
