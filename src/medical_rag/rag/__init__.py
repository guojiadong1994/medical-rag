"""Public exports for the RAG package.

Keep this package initializer lightweight.

Why: ``generation.models`` imports ``medical_rag.rag.context``. Python executes
``medical_rag.rag.__init__`` before loading the submodule. If this initializer
eagerly imports ``rag.pipeline``, the pipeline imports ``generation.client`` and
creates a circular import:

    generation.client -> generation.models -> rag.context
    -> rag.__init__ -> rag.pipeline -> generation.client

Context/prompt objects are safe to export eagerly. Product pipeline objects are
exported lazily through ``__getattr__`` so existing callers can still write
``from medical_rag.rag import MedicalRAGPipeline`` without forcing the pipeline
to load during unrelated submodule imports.
"""

from __future__ import annotations

from typing import Any

from medical_rag.rag.context import (
    CitationValidationResult,
    ContextBuilderConfig,
    RAGCitation,
    RAGContext,
    RAGContextBuilder,
    RAGContextSource,
    citation_summary_lines,
    validate_answer_citations,
)
from medical_rag.rag.prompt import (
    DEFAULT_GROUNDED_SYSTEM_PROMPT,
    GroundedPromptBuilder,
    RAGPrompt,
)

_PIPELINE_EXPORTS = {
    "MedicalRAGPipeline",
    "RAGDiagnostics",
    "RAGPipelineConfigurationError",
    "RAGRequest",
    "RAGResponse",
    "RAGSource",
    "RAGTiming",
}


def __getattr__(name: str) -> Any:
    """Load product pipeline symbols only when they are actually requested."""

    if name in _PIPELINE_EXPORTS:
        from medical_rag.rag import pipeline as _pipeline

        value = getattr(_pipeline, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | _PIPELINE_EXPORTS)


__all__ = [
    "RAGRequest",
    "RAGResponse",
    "RAGSource",
    "RAGTiming",
    "RAGDiagnostics",
    "RAGPipelineConfigurationError",
    "MedicalRAGPipeline",
    "RAGCitation",
    "RAGContextSource",
    "RAGContext",
    "ContextBuilderConfig",
    "RAGContextBuilder",
    "CitationValidationResult",
    "validate_answer_citations",
    "citation_summary_lines",
    "RAGPrompt",
    "GroundedPromptBuilder",
    "DEFAULT_GROUNDED_SYSTEM_PROMPT",
]
