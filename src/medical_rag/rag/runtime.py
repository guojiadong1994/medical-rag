from __future__ import annotations

import threading
from dataclasses import dataclass

from medical_rag.core.config import Settings, get_settings
from medical_rag.rag.pipeline import MedicalRAGPipeline, RAGPipelineConfigurationError


@dataclass(frozen=True)
class PipelineRuntimeStatus:
    loaded: bool
    loading: bool
    error: str | None


_pipeline: MedicalRAGPipeline | None = None
_pipeline_error: str | None = None
_loading = False
_lock = threading.Lock()


def get_pipeline(*, settings: Settings | None = None) -> MedicalRAGPipeline:
    global _pipeline, _pipeline_error, _loading
    if _pipeline is not None:
        return _pipeline

    with _lock:
        if _pipeline is not None:
            return _pipeline
        _loading = True
        try:
            _pipeline = MedicalRAGPipeline.from_settings(settings or get_settings())
            _pipeline_error = None
            return _pipeline
        except Exception as exc:
            _pipeline_error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            _loading = False


def get_runtime_status() -> PipelineRuntimeStatus:
    return PipelineRuntimeStatus(
        loaded=_pipeline is not None,
        loading=_loading,
        error=_pipeline_error,
    )


def reset_pipeline() -> None:
    global _pipeline, _pipeline_error, _loading
    with _lock:
        _pipeline = None
        _pipeline_error = None
        _loading = False


def reset_pipeline_for_tests() -> None:
    reset_pipeline()


__all__ = [
    "PipelineRuntimeStatus",
    "RAGPipelineConfigurationError",
    "get_pipeline",
    "get_runtime_status",
    "reset_pipeline",
    "reset_pipeline_for_tests",
]
