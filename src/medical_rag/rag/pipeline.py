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
    async def run(self, request: RAGRequest) -> RAGResponse:
        raise NotImplementedError("Medical knowledge retrieval pipeline is not configured.")
