from __future__ import annotations

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.io import text_sha256
from medical_rag.embedding.models import ChunkEmbeddingRef, EmbeddingManifest
from medical_rag.evaluation import EvidenceRule, RetrievalEvalCase, RetrievalEvalSuite, diagnose_recall
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex


class FakeEmbedder:
    model_name = "fake"
    dimension = 2

    def encode_query(self, text: str):
        if "目标" in text:
            return np.array([1.0, 0.0], dtype=np.float32)
        return np.array([0.0, 1.0], dtype=np.float32)


def _chunk(idx: int, text: str, page: int) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"c{idx}",
        document_id="d",
        source_file="x.pdf",
        content_type="narrative",
        section="4.5.1",
        section_path=["4.5.1"],
        page_start=page,
        page_end=page,
        text=text,
        embedding_text=text,
        char_count=len(text),
    )


def test_diagnosis_separates_missing_evidence_from_retrieval_ranking():
    chunks = [
        _chunk(0, "无关内容", 1),
        _chunk(1, "目标证据 135/85", 10),
        _chunk(2, "其他内容", 2),
    ]
    embeddings = np.array(
        [
            [0.0, 1.0],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )
    manifest = EmbeddingManifest(
        document_id="d",
        source_file="x.pdf",
        model_name="fake",
        dimension=2,
        normalized=True,
        dtype="float32",
        chunk_count=3,
        refs=[
            ChunkEmbeddingRef(chunk_id=c.chunk_id, text_sha256=text_sha256(c.embedding_text))
            for c in chunks
        ],
    )

    dense = LocalDenseIndex(chunks=chunks, embeddings=embeddings, manifest=manifest)
    bm25 = LocalBM25Index(chunks=chunks)
    suite = RetrievalEvalSuite(
        name="smoke",
        cases=[
            RetrievalEvalCase(
                id="present",
                query="目标证据是多少",
                evidence_rules=[EvidenceRule(page_ranges=[(10, 10)], required_keywords=["135/85"])],
            ),
            RetrievalEvalCase(
                id="missing",
                query="不存在的证据",
                evidence_rules=[EvidenceRule(page_ranges=[(99, 99)], required_keywords=["不存在"])],
            ),
        ],
    )

    result = diagnose_recall(
        suite,
        dense_index=dense,
        bm25_index=bm25,
        embedder=FakeEmbedder(),
        top_k=1,
        candidate_k=1,
        deep_k=3,
    )
    assert result[0].category == "HIT"
    assert result[0].evidence_chunk_count == 1
    assert result[1].category == "EVIDENCE_MISSING_FROM_CHUNKS"
    assert result[1].evidence_chunk_count == 0
