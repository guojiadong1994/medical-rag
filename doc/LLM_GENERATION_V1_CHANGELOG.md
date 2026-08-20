# LLM Generation V1 Changelog

## 新增

- `src/medical_rag/generation/client.py`
  - `OpenAICompatibleConfig`
  - `OpenAICompatibleChatClient`
  - `LLMGenerationError`
- `src/medical_rag/generation/models.py`
  - LLM response / usage / generation result models
- `src/medical_rag/generation/service.py`
  - `GroundedAnswerGenerator`
  - 无证据时 deterministic abstention
  - Citation structural grounding check
- `scripts/generate_rag_answer.py`
  - 完整 Retrieval -> Generation CLI
- `tests/unit/test_generation_v1.py`
- `doc/LLM_GENERATION_V1.md`

## 设计原则

- 不修改已验证的 Chunk / Embedding / Hybrid / Reranker 算法；
- 不把 API key 写进日志和产物；
- LLM endpoint 与 RAG 业务逻辑解耦；
- 没有证据时不调用模型；
- Citation V1 只做结构校验，不虚假宣称已经完成语义级 faithfulness 验证。
