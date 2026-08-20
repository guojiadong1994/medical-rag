from __future__ import annotations

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.io import build_refs
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.retrieval.milvus_dense import (
    MilvusDenseIndex,
    build_milvus_filter,
    chunk_to_milvus_record,
    compare_dense_rankings,
)
from medical_rag.retrieval.models import DenseSearchHit, DenseSearchResponse


def _chunk(chunk_id: str = "c1") -> DocumentChunk:
    text = "2级高血压舒张压100~109 mmHg。"
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id="doc",
        source_file="guide.pdf",
        content_type="table",
        section="4.5.1 按血压水平分类和分级",
        section_path=["要点4", "4.5.1 按血压水平分类和分级"],
        page_start=10,
        page_end=10,
        text=text,
        embedding_text=f"章节：4.5.1 按血压水平分类和分级\n\n{text}",
        char_count=len(text),
        table_title="表6",
        table_no=0,
    )


def _manifest(chunks: list[DocumentChunk]) -> EmbeddingManifest:
    return EmbeddingManifest(
        document_id="doc",
        source_file="guide.pdf",
        model_name="dummy",
        dimension=2,
        normalized=True,
        chunk_count=len(chunks),
        refs=build_refs(chunks),
    )


def test_build_milvus_filter_supports_metadata_and_page_overlap() -> None:
    expression = build_milvus_filter(
        document_id='doc"1',
        content_type="table",
        page=10,
    )
    assert 'document_id == "doc\\\"1"' in expression
    assert 'content_type == "table"' in expression
    assert "page_start <= 10" in expression
    assert "page_end >= 10" in expression


def test_chunk_to_milvus_record_preserves_vector_and_chunk_metadata() -> None:
    chunks = [_chunk()]
    manifest = _manifest(chunks)
    record = chunk_to_milvus_record(chunks[0], np.asarray([0.6, 0.8]), manifest)

    assert record["chunk_id"] == "c1"
    assert record["vector"] == [0.6000000238418579, 0.800000011920929]
    assert record["content_type"] == "table"
    assert record["table_no"] == 0
    assert "4.5.1" in record["section_path_json"]
    assert record["embedding_model"] == "dummy"


class _FakeClient:
    def __init__(self) -> None:
        self.search_kwargs = None
        self.loaded = False

    def load_collection(self, *, collection_name: str) -> None:
        assert collection_name == "chunks"
        self.loaded = True

    def search(self, **kwargs):
        self.search_kwargs = kwargs
        return [
            [
                {
                    "id": "c1",
                    "distance": 0.91,
                    "entity": {
                        "chunk_id": "c1",
                        "document_id": "doc",
                        "source_file": "guide.pdf",
                        "content_type": "table",
                        "section": "4.5.1 按血压水平分类和分级",
                        "section_path_json": '["要点4", "4.5.1 按血压水平分类和分级"]',
                        "page_start": 10,
                        "page_end": 10,
                        "text": "2级高血压舒张压100~109 mmHg。",
                        "table_title": "表6",
                        "table_no": 0,
                    },
                }
            ]
        ]


class _DummyEmbedder:
    model_name = "dummy"
    dimension = 2
    device = "cpu"

    def encode_query(self, text: str) -> np.ndarray:
        return np.asarray([3.0, 4.0], dtype=np.float32)

    def encode_documents(self, texts):  # pragma: no cover - unused
        raise NotImplementedError


def test_milvus_search_maps_result_to_existing_dense_response_model() -> None:
    chunks = [_chunk()]
    client = _FakeClient()
    index = MilvusDenseIndex(
        uri="fake.db",
        collection_name="chunks",
        manifest=_manifest(chunks),
        client=client,
    )
    response = index.search(
        "二级高血压舒张压是多少？",
        embedder=_DummyEmbedder(),
        top_k=5,
        filter_expr='content_type == "table"',
    )

    assert client.loaded is True
    assert client.search_kwargs["filter"] == 'content_type == "table"'
    # 3-4-5 vector is normalized before Milvus search because the stored corpus is normalized.
    assert np.allclose(client.search_kwargs["data"][0], [0.6, 0.8])
    assert response.hits[0].chunk_id == "c1"
    assert response.hits[0].score == 0.91
    assert response.hits[0].table_title == "表6"


def _response(ids: list[str]) -> DenseSearchResponse:
    hits = [
        DenseSearchHit(
            rank=rank,
            score=1.0 / rank,
            chunk_id=chunk_id,
            document_id="doc",
            source_file="guide.pdf",
            content_type="narrative",
            section=None,
            section_path=[],
            page_start=1,
            page_end=1,
            text=chunk_id,
        )
        for rank, chunk_id in enumerate(ids, start=1)
    ]
    return DenseSearchResponse(query="q", model_name="dummy", top_k=len(hits), hits=hits)


def test_compare_dense_rankings_reports_overlap_separately_from_exact_order() -> None:
    comparison = compare_dense_rankings(
        _response(["a", "b", "c"]),
        _response(["a", "c", "b"]),
    )
    assert comparison["overlap_ratio"] == 1.0
    assert comparison["same_rank_ratio"] == 0.333333
    assert comparison["first_rank_mismatch"] == 2
