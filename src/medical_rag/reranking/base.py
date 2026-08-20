from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class TextReranker(Protocol):
    """Minimal interface for pairwise query-document rerankers."""

    @property
    def model_name(self) -> str: ...

    @property
    def device(self) -> str: ...

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        """Return one relevance score per document; larger means more relevant."""
        ...
