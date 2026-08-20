from __future__ import annotations

import json
from pathlib import Path

from medical_rag.core.config import get_settings


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
    errors = settings.rag_readiness_errors()
    payload = {
        "ready_for_pipeline_initialization": not errors,
        "dense_backend": settings.rag_dense_backend,
        "paths": paths,
        "llm_base_url_configured": bool(settings.medical_rag_llm_base_url.strip()),
        "llm_model": settings.medical_rag_llm_model or None,
        "configuration_errors": errors,
        "next_action": (
            "python run.py"
            if not errors
            else "Fix the configuration errors above before starting the API."
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
