# Architecture

```text
Doctor Web
    |
 FastAPI
    |
 Query Router
    |
 +----------------------+-----------------------+
 |                      |                       |
Patient Retrieval   Medical Knowledge      Multimodal Report
 |                      |                       |
Timeline            BM25 + Dense           Image Caption
 |                      |                       |
 +----------------------+-----------------------+
                        |
                 RRF + Reranker
                        |
                  Context Builder
                        |
                       LLM
                        |
              Citation / Safety Guard
```

基础设施：

- PostgreSQL：患者、文档、时间线、权限、审计
- Redis：Cache / Session / Task State
- MinIO：PDF、图片、解析产物
- Milvus：Phase 2
- Neo4j：Phase 6
- vLLM：Phase 9
