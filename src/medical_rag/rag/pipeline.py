from dataclasses import dataclass


@dataclass(slots=True)
class RAGRequest:
    query: str
    patient_id: str | None = None


@dataclass(slots=True)
class RAGResponse:
    answer: str
    citations: list[str]


class MedicalRAGPipeline:
    # Phase 0 placeholder.
    # Planned chain:
    # Query Router -> Metadata Filter -> Hybrid Retrieval
    # -> RRF -> Reranker -> Context Builder -> LLM -> Citation Guard

    async def run(self, request: RAGRequest) -> RAGResponse:
        raise NotImplementedError("RAG pipeline will be implemented from Phase 2.")
