from __future__ import annotations

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.io import build_refs
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def _chunk(chunk_id: str, text: str, section: str) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id="doc",
        source_file="guide.pdf",
        content_type="narrative",
        section=section,
        section_path=[section],
        page_start=1,
        page_end=1,
        text=text,
        embedding_text=f"章节：{section}\n\n{text}",
        char_count=len(text),
    )


def test_bm25_preserves_medical_numbers_and_chinese_level_alias() -> None:
    chunks = [
        _chunk("c1", "2级高血压舒张压100~109 mmHg。", "血压分类"),
        _chunk("c2", "高血压患者应限制钠盐摄入。", "生活方式"),
    ]
    index = LocalBM25Index(chunks=chunks)
    result = index.search("二级高血压舒张压100~109是多少", top_k=2)
    assert result.hits[0].chunk_id == "c1"


def test_rrf_promotes_chunk_supported_by_both_channels() -> None:
    chunks = [
        _chunk("c1", "2级高血压舒张压100~109 mmHg。", "血压分类"),
        _chunk("c2", "儿童青少年正常高值血压需结合年龄判断。", "儿童青少年"),
        _chunk("c3", "高血压患者应限制钠盐摄入。", "生活方式"),
    ]
    matrix = np.asarray([[0.9, 0.1], [1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    manifest = EmbeddingManifest(
        document_id="doc",
        source_file="guide.pdf",
        model_name="dummy",
        dimension=2,
        normalized=True,
        chunk_count=len(chunks),
        refs=build_refs(chunks),
    )
    dense = LocalDenseIndex(chunks=chunks, embeddings=matrix, manifest=manifest)
    bm25 = LocalBM25Index(chunks=chunks)

    class DummyEmbedder:
        model_name = "dummy"
        dimension = 2
        device = "cpu"

        def encode_query(self, text: str) -> np.ndarray:
            return np.asarray([1.0, 0.0], dtype=np.float32)

        def encode_documents(self, texts):  # pragma: no cover - unused in search test
            raise NotImplementedError

    hybrid = ReciprocalRankFusionIndex(
        dense_index=dense,
        bm25_index=bm25,
        embedder=DummyEmbedder(),
        candidate_k=3,
    )
    result = hybrid.search("二级高血压舒张压100~109是多少", top_k=3)
    assert result.hits[0].chunk_id == "c1"
    assert result.hits[0].dense_rank is not None
    assert result.hits[0].bm25_rank == 1
