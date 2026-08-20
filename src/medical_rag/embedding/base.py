from __future__ import annotations

from typing import Protocol, Sequence

import numpy as np


class TextEmbedder(Protocol):
    """Minimal interface shared by embedding backends."""

    @property
    def model_name(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...

    @property
    def device(self) -> str:
        ...

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        """Encode document/chunk texts into a 2-D float32 matrix."""
        ...

    def encode_query(self, text: str) -> np.ndarray:
        """Encode one retrieval query into a 1-D float32 vector."""
        ...
