from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.core.paths import project_path
from medical_rag.embedding.io import (
    build_refs,
    load_chunks,
    load_embedding_matrix,
    load_manifest,
    validate_chunks_against_manifest,
)
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.ingestion.registry import KnowledgeRegistry


@dataclass(frozen=True)
class KnowledgeBaseArtifacts:
    chunks: list[DocumentChunk]
    embeddings: np.ndarray
    manifest: EmbeddingManifest
    document_count: int


def _artifact_dirs(
    *,
    legacy_chunks_path: Path,
    registry: KnowledgeRegistry,
) -> list[Path]:
    directories: list[Path] = []
    legacy_dir = legacy_chunks_path.parent
    if (legacy_dir / "chunks.json").exists():
        directories.append(legacy_dir)

    for record in registry.list():
        if record.status != "ready":
            continue
        directory = project_path(record.processed_dir)
        if directory not in directories:
            directories.append(directory)
    return directories


def load_knowledge_base_artifacts(
    *,
    legacy_chunks_path: Path,
    legacy_embeddings_path: Path,
    legacy_manifest_path: Path,
    registry: KnowledgeRegistry | None = None,
) -> KnowledgeBaseArtifacts:
    """Load all ready local knowledge documents into one in-memory exact index.

    Existing hypertension_2024 artifacts are treated as the legacy first
    document, so upgrading to automatic ingestion does not require rebuilding
    the already verified guide. Newly uploaded documents live independently
    under data/processed/knowledge_documents/<document_id> and are concatenated
    only when the query service initializes.
    """

    registry = registry or KnowledgeRegistry()
    legacy_chunks_path = project_path(legacy_chunks_path)
    legacy_embeddings_path = project_path(legacy_embeddings_path)
    legacy_manifest_path = project_path(legacy_manifest_path)

    candidates = _artifact_dirs(
        legacy_chunks_path=legacy_chunks_path,
        registry=registry,
    )
    if not candidates:
        raise FileNotFoundError("no ready knowledge documents were found")

    all_chunks: list[DocumentChunk] = []
    matrices: list[np.ndarray] = []
    seen_document_ids: set[str] = set()
    model_name: str | None = None
    dimension: int | None = None
    normalized: bool | None = None

    for directory in candidates:
        chunks_path = directory / "chunks.json"
        embeddings_path = directory / "embeddings.npy"
        manifest_path = directory / "embedding_manifest.json"
        if not (chunks_path.exists() and embeddings_path.exists() and manifest_path.exists()):
            continue

        chunks = load_chunks(chunks_path)
        manifest = load_manifest(manifest_path)
        validate_chunks_against_manifest(chunks, manifest)
        if not chunks:
            continue
        document_id = chunks[0].document_id
        if document_id in seen_document_ids:
            continue

        matrix = load_embedding_matrix(embeddings_path, manifest)
        if model_name is None:
            model_name = manifest.model_name
            dimension = manifest.dimension
            normalized = manifest.normalized
        elif (
            manifest.model_name != model_name
            or manifest.dimension != dimension
            or manifest.normalized != normalized
        ):
            raise ValueError(
                "knowledge documents use incompatible embedding settings; "
                "re-embed them with the same model before publishing"
            )

        all_chunks.extend(chunks)
        matrices.append(matrix)
        seen_document_ids.add(document_id)

    if not all_chunks or not matrices or model_name is None or dimension is None:
        raise FileNotFoundError("ready knowledge documents exist but no complete embedding artifacts were found")

    embeddings = np.ascontiguousarray(np.concatenate(matrices, axis=0), dtype=np.float32)
    manifest = EmbeddingManifest(
        document_id="knowledge_base",
        source_file="MULTI_DOCUMENT_KNOWLEDGE_BASE",
        model_name=model_name,
        dimension=dimension,
        normalized=bool(normalized),
        dtype="float32",
        chunk_count=len(all_chunks),
        refs=build_refs(all_chunks),
    )
    return KnowledgeBaseArtifacts(
        chunks=all_chunks,
        embeddings=embeddings,
        manifest=manifest,
        document_count=len(seen_document_ids),
    )


__all__ = ["KnowledgeBaseArtifacts", "load_knowledge_base_artifacts"]
