from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.io import build_refs
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.ingestion.registry import KnowledgeDocumentRecord, KnowledgeRegistry
from medical_rag.ingestion.store import load_knowledge_base_artifacts


def _write_doc(directory: Path, *, document_id: str, source_file: str, value: float) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    chunk = DocumentChunk(
        chunk_id=f"{document_id}_txt_00000",
        document_id=document_id,
        source_file=source_file,
        content_type="narrative",
        section="测试章节",
        section_path=["测试章节"],
        page_start=1,
        page_end=1,
        text=f"{source_file} 测试文本",
        embedding_text=f"{source_file} 测试文本",
        char_count=10,
    )
    (directory / "chunks.json").write_text(
        json.dumps([chunk.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )
    matrix = np.full((1, 4), value, dtype=np.float32)
    np.save(directory / "embeddings.npy", matrix, allow_pickle=False)
    manifest = EmbeddingManifest(
        document_id=document_id,
        source_file=source_file,
        model_name="fake-embed",
        dimension=4,
        normalized=True,
        chunk_count=1,
        refs=build_refs([chunk]),
    )
    (directory / "embedding_manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )


def test_registry_persists_processing_state(tmp_path: Path):
    registry = KnowledgeRegistry(tmp_path / "registry.json")
    record = KnowledgeDocumentRecord(
        id="doc1",
        name="指南.pdf",
        category="临床指南",
        size_bytes=100,
        uploaded_at="2026-08-20 20:00:00",
        updated_at="2026-08-20 20:00:00",
        source_path=str(tmp_path / "指南.pdf"),
        processed_dir=str(tmp_path / "processed"),
        status="uploaded",
        progress=5,
        stage_message="等待处理",
    )
    registry.upsert(record)
    updated = registry.update(
        "doc1",
        status="embedding",
        progress=70,
        stage_message="正在生成语义向量",
    )
    assert updated.status == "embedding"
    assert updated.progress == 70
    assert KnowledgeRegistry(tmp_path / "registry.json").get("doc1").stage_message == "正在生成语义向量"


def test_local_knowledge_store_combines_legacy_and_ready_documents(tmp_path: Path):
    legacy = tmp_path / "legacy"
    extra = tmp_path / "extra"
    _write_doc(legacy, document_id="legacy-doc", source_file="legacy.pdf", value=0.5)
    _write_doc(extra, document_id="extra-doc", source_file="extra.pdf", value=0.25)

    registry = KnowledgeRegistry(tmp_path / "registry.json")
    registry.upsert(
        KnowledgeDocumentRecord(
            id="record-extra",
            name="extra.pdf",
            category="临床指南",
            size_bytes=100,
            uploaded_at="2026-08-20 20:00:00",
            updated_at="2026-08-20 20:00:00",
            source_path=str(tmp_path / "extra.pdf"),
            processed_dir=str(extra),
            status="ready",
            progress=100,
            stage_message="已索引",
            chunk_count=1,
        )
    )

    result = load_knowledge_base_artifacts(
        legacy_chunks_path=legacy / "chunks.json",
        legacy_embeddings_path=legacy / "embeddings.npy",
        legacy_manifest_path=legacy / "embedding_manifest.json",
        registry=registry,
    )
    assert result.document_count == 2
    assert len(result.chunks) == 2
    assert result.embeddings.shape == (2, 4)
    assert result.manifest.chunk_count == 2
    assert {chunk.source_file for chunk in result.chunks} == {"legacy.pdf", "extra.pdf"}
