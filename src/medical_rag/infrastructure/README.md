# infrastructure

PostgreSQL、Redis、Milvus、MinIO 等基础设施适配。

当前 Milvus V1 采用 `MilvusClient`，默认先使用 Milvus Lite 本地持久化文件；同一检索代码后续可通过替换 URI 迁移到 Milvus Standalone / Distributed。
