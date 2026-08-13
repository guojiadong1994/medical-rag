from typing import Protocol


class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> str:
        ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class VisionLanguageProvider(Protocol):
    async def describe_image(self, image_uri: str, prompt: str) -> str:
        ...


class RerankerProvider(Protocol):
    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        ...
