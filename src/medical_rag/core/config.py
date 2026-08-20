from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from medical_rag.core.paths import project_path


class Settings(BaseSettings):
    """Application and Product V1 runtime settings.

    Environment variable names are the upper-case form of these fields. Existing
    LLM variables such as ``MEDICAL_RAG_LLM_BASE_URL`` therefore continue to work.
    """

    app_name: str = "medical-rag"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    doctor_username: str = "doctor"
    doctor_password: str = "123456"
    access_token: str = "medical-rag-doctor-session"

    # RAG data produced by the existing ingestion/embedding pipeline.
    rag_chunks_path: str = "data/processed/hypertension_2024/chunks.json"
    rag_embeddings_path: str = "data/processed/hypertension_2024/embeddings.npy"
    rag_manifest_path: str = "data/processed/hypertension_2024/embedding_manifest.json"

    # Local exact retrieval is the default for the single-node macOS product.
    # Milvus remains available for Linux/server deployment via RAG_DENSE_BACKEND=milvus.
    rag_dense_backend: Literal["milvus", "local"] = "local"
    rag_milvus_uri: str = "data/milvus/medical_rag.db"
    rag_milvus_collection: str = "medical_rag_chunks_v1"
    rag_milvus_token: str | None = None

    rag_embedding_model: str = "BAAI/bge-m3"
    rag_embedding_device: str | None = None
    rag_embedding_batch_size: int = 8

    rag_reranker_model: str = "BAAI/bge-reranker-base"
    rag_reranker_device: str = "auto"
    rag_reranker_batch_size: int = 4
    rag_reranker_max_length: int = 512

    rag_candidate_k: int = 50
    rag_rrf_k: int = 60
    rag_rerank_k: int = 20
    rag_context_top_k: int = 5
    rag_max_context_chars: int = 6000

    # OpenAI-compatible LLM endpoint. These names intentionally match the
    # environment variables already used in Generation V1.
    medical_rag_llm_base_url: str = ""
    medical_rag_llm_model: str = ""
    medical_rag_llm_api_key: str | None = None
    medical_rag_llm_temperature: float = 0.0
    medical_rag_llm_max_output_tokens: int = 768
    medical_rag_llm_timeout_seconds: float = 90.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def chunks_path(self) -> Path:
        return project_path(self.rag_chunks_path)

    @property
    def embeddings_path(self) -> Path:
        return project_path(self.rag_embeddings_path)

    @property
    def manifest_path(self) -> Path:
        return project_path(self.rag_manifest_path)

    def rag_readiness_errors(self) -> list[str]:
        errors: list[str] = []
        if self.rag_dense_backend == "milvus":
            for label, path in (
                ("chunks", self.chunks_path),
                ("embedding manifest", self.manifest_path),
            ):
                if not path.exists():
                    errors.append(f"{label} file not found: {path}")
        else:
            # The local backend can load the legacy verified guide and any
            # automatically processed documents from the knowledge registry.
            from medical_rag.ingestion.store import load_knowledge_base_artifacts

            try:
                load_knowledge_base_artifacts(
                    legacy_chunks_path=self.chunks_path,
                    legacy_embeddings_path=self.embeddings_path,
                    legacy_manifest_path=self.manifest_path,
                )
            except (FileNotFoundError, ValueError) as exc:
                errors.append(f"knowledge base artifacts are not ready: {exc}")
        if not self.medical_rag_llm_base_url.strip():
            errors.append("MEDICAL_RAG_LLM_BASE_URL is not configured")
        if not self.medical_rag_llm_model.strip():
            errors.append("MEDICAL_RAG_LLM_MODEL is not configured")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()
