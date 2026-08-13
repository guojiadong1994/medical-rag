from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RetrievalHit:
    chunk_id: str
    score: float
    text: str
    metadata: dict


class Retriever(Protocol):
    async def search(
        self,
        query: str,
        *,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[RetrievalHit]:
        ...
