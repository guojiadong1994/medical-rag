# Retrieval Evaluation V1 Changelog

- 新增本地 Dense Retrieval 自动评测：Recall@1 / @3 / @5 / MRR。
- 新增高血压指南小型人工评测种子集。
- 修复 SentenceTransformers `get_sentence_embedding_dimension` 的 FutureWarning。
- 收紧纯整数章节识别，降低 `95 定义为高血压...` 一类正文被误识别为 Section 的概率。
