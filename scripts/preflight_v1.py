from __future__ import annotations

import importlib
import json

from medical_rag.core.config import get_settings
from medical_rag.core.paths import project_path
from medical_rag.ingestion.registry import KnowledgeRegistry


def _check_api_import() -> tuple[bool, str | None]:
    """Smoke-test the API import without loading the heavy RAG models."""

    try:
        importlib.import_module("medical_rag.api.app")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def main() -> int:
    settings = get_settings()
    registry = KnowledgeRegistry()
    ready_documents = [item for item in registry.list() if item.status == "ready"]
    legacy_ready = (
        settings.chunks_path.exists()
        and settings.manifest_path.exists()
        and settings.embeddings_path.exists()
    )
    paths = {
        "legacy_chunks": settings.chunks_path.exists(),
        "legacy_manifest": settings.manifest_path.exists(),
        "legacy_embeddings": settings.embeddings_path.exists(),
        "milvus_file": (
            project_path(settings.rag_milvus_uri).exists()
            if "://" not in settings.rag_milvus_uri
            else True
        ),
        "knowledge_registry": project_path("data/knowledge/registry.json").exists(),
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
        "legacy_verified_document_ready": legacy_ready,
        "auto_ingested_ready_document_count": len(ready_documents),
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
