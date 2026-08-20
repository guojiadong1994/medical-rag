from __future__ import annotations

import importlib
import json
from pathlib import Path

from medical_rag.core.config import get_settings


def _check_api_import() -> tuple[bool, str | None]:
    """Smoke-test the API import without loading the heavy RAG models.

    This catches startup failures such as circular imports before the user runs
    ``python run.py``. Importing the FastAPI application creates routes/settings
    only; the embedding/reranker models are still loaded lazily on first RAG use.
    """

    try:
        importlib.import_module("medical_rag.api.app")
    except Exception as exc:  # preflight should report, not hide, startup blockers
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def main() -> int:
    settings = get_settings()
    paths = {
        "chunks": Path(settings.rag_chunks_path).exists(),
        "manifest": Path(settings.rag_manifest_path).exists(),
        "embeddings": Path(settings.rag_embeddings_path).exists(),
        "milvus_file": (
            Path(settings.rag_milvus_uri).exists()
            if "://" not in settings.rag_milvus_uri
            else True
        ),
    }
    errors = list(settings.rag_readiness_errors())
    api_importable, api_import_error = _check_api_import()
    if not api_importable:
        errors.append(f"API startup import failed: {api_import_error}")

    ready = not errors
    payload = {
        "ready_for_pipeline_initialization": ready,
        "api_importable": api_importable,
        "api_import_error": api_import_error,
        "dense_backend": settings.rag_dense_backend,
        "paths": paths,
        "llm_base_url_configured": bool(settings.medical_rag_llm_base_url.strip()),
        "llm_model": settings.medical_rag_llm_model or None,
        "configuration_errors": errors,
        "next_action": (
            "python run.py"
            if ready
            else "Fix the configuration/startup errors above before starting the API."
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
