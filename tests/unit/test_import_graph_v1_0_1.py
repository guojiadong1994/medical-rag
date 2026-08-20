from __future__ import annotations

import importlib


def test_generation_client_can_import_before_rag_pipeline():
    """Regression: generation -> rag.context must not eagerly pull rag.pipeline."""

    module = importlib.import_module("medical_rag.generation.client")
    assert hasattr(module, "OpenAICompatibleChatClient")


def test_rag_root_keeps_lazy_pipeline_exports():
    """Public root imports stay compatible while pipeline loading is lazy."""

    rag = importlib.import_module("medical_rag.rag")
    assert rag.ContextBuilderConfig is not None
    assert "MedicalRAGPipeline" in dir(rag)
