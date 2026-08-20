# Reranking

当前 V1 使用两阶段检索：

1. Dense + BM25 -> RRF，优先保证候选召回；
2. Cross-Encoder Reranker 对 RRF 前若干候选重新打分，提升前排排序质量。

默认实验模型为 `BAAI/bge-reranker-base`，默认只重排 RRF Top 20。
