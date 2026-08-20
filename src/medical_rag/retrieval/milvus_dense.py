from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.base import TextEmbedder
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.retrieval.models import DenseSearchHit, DenseSearchResponse


DEFAULT_MILVUS_COLLECTION = "medical_rag_chunks_v1"
DEFAULT_MILVUS_URI = "data/milvus/medical_rag.db"
MILVUS_VECTOR_FIELD = "vector"
MILVUS_METRIC_TYPE = "COSINE"

_OUTPUT_FIELDS = [
    "chunk_id",
    "document_id",
    "source_file",
    "content_type",
    "section",
    "section_path_json",
    "page_start",
    "page_end",
    "text",
    "table_title",
    "table_no",
    "embedding_model",
    "embedding_normalized",
]


def _import_pymilvus() -> tuple[Any, Any]:
    try:
        from pymilvus import DataType, MilvusClient
    except ImportError as exc:  # pragma: no cover - depends on optional dependency
        raise RuntimeError(
            "Milvus support is not installed. Run: pip install -e \".[milvus]\""
        ) from exc
    return MilvusClient, DataType


def ensure_local_milvus_parent(uri: str) -> None:
    """Create the parent directory when `uri` points to a Milvus Lite file."""

    if "://" in uri:
        return
    path = Path(uri).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)


def _json_string_literal(value: str) -> str:
    # Milvus filter expressions accept quoted string literals. json.dumps gives
    # us deterministic escaping for quotes, backslashes, and non-ASCII text.
    return json.dumps(value, ensure_ascii=False)


def build_milvus_filter(
    *,
    document_id: str | None = None,
    source_file: str | None = None,
    content_type: str | None = None,
    section: str | None = None,
    page: int | None = None,
) -> str | None:
    """Build a conservative scalar metadata filter for dense search.

    `page=N` means the chunk overlaps page N, therefore both start/end fields
    participate in the expression.
    """

    clauses: list[str] = []
    for field, value in (
        ("document_id", document_id),
        ("source_file", source_file),
        ("content_type", content_type),
        ("section", section),
    ):
        if value is not None:
            clauses.append(f"{field} == {_json_string_literal(value)}")

    if page is not None:
        if page <= 0:
            raise ValueError("page must be positive")
        clauses.append(f"page_start <= {page}")
        clauses.append(f"page_end >= {page}")

    return " and ".join(clauses) if clauses else None


def chunk_to_milvus_record(
    chunk: DocumentChunk,
    vector: np.ndarray,
    manifest: EmbeddingManifest,
) -> dict[str, Any]:
    vector = np.asarray(vector, dtype=np.float32)
    if vector.shape != (manifest.dimension,):
        raise ValueError(
            f"vector shape mismatch for {chunk.chunk_id}: "
            f"expected {(manifest.dimension,)}, got {vector.shape}"
        )
    if not np.isfinite(vector).all():
        raise ValueError(f"vector for {chunk.chunk_id} contains NaN or infinity")

    return {
        "chunk_id": chunk.chunk_id,
        "vector": vector.tolist(),
        "document_id": chunk.document_id,
        "source_file": chunk.source_file,
        "content_type": chunk.content_type,
        "section": chunk.section or "",
        "section_path_json": json.dumps(chunk.section_path, ensure_ascii=False),
        "page_start": int(chunk.page_start),
        "page_end": int(chunk.page_end),
        "text": chunk.text,
        "embedding_text": chunk.embedding_text,
        "table_title": chunk.table_title or "",
        "table_no": int(chunk.table_no) if chunk.table_no is not None else -1,
        "metadata_json": json.dumps(chunk.metadata, ensure_ascii=False),
        "embedding_model": manifest.model_name,
        "embedding_normalized": bool(manifest.normalized),
    }


def iter_milvus_records(
    chunks: list[DocumentChunk],
    embeddings: np.ndarray,
    manifest: EmbeddingManifest,
) -> Iterable[dict[str, Any]]:
    matrix = np.asarray(embeddings, dtype=np.float32)
    expected = (len(chunks), manifest.dimension)
    if matrix.shape != expected:
        raise ValueError(f"embedding matrix shape mismatch: expected {expected}, got {matrix.shape}")
    for chunk, vector in zip(chunks, matrix, strict=True):
        yield chunk_to_milvus_record(chunk, vector, manifest)


def _extract_dimension(description: Any) -> int | None:
    """Best-effort schema inspection across recent pymilvus response shapes."""

    if not isinstance(description, dict):
        return None
    fields = description.get("fields") or description.get("schema", {}).get("fields") or []
    for field in fields:
        if not isinstance(field, dict):
            continue
        name = field.get("name") or field.get("field_name")
        if name != MILVUS_VECTOR_FIELD:
            continue
        candidates = [
            field.get("dim"),
            (field.get("params") or {}).get("dim") if isinstance(field.get("params"), dict) else None,
            (field.get("type_params") or {}).get("dim")
            if isinstance(field.get("type_params"), dict)
            else None,
        ]
        for value in candidates:
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
    return None


@dataclass(frozen=True)
class MilvusIngestSummary:
    uri: str
    collection_name: str
    chunk_count: int
    dimension: int
    model_name: str
    normalized: bool
    batch_size: int
    operation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "collection_name": self.collection_name,
            "chunk_count": self.chunk_count,
            "dimension": self.dimension,
            "model_name": self.model_name,
            "normalized": self.normalized,
            "batch_size": self.batch_size,
            "operation": self.operation,
        }


class MilvusDenseIndex:
    """Dense retrieval backend backed by MilvusClient.

    The same class works with:
    - Milvus Lite: uri="data/milvus/medical_rag.db"
    - Milvus Standalone/Distributed: uri="http://localhost:19530"
    """

    def __init__(
        self,
        *,
        uri: str = DEFAULT_MILVUS_URI,
        collection_name: str = DEFAULT_MILVUS_COLLECTION,
        manifest: EmbeddingManifest,
        token: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.uri = uri
        self.collection_name = collection_name
        self.manifest = manifest

        if client is None:
            ensure_local_milvus_parent(uri)
            MilvusClient, _ = _import_pymilvus()
            kwargs: dict[str, Any] = {"uri": uri}
            if token:
                kwargs["token"] = token
            client = MilvusClient(**kwargs)
        self.client = client

    def ensure_collection(self, *, recreate: bool = False) -> bool:
        """Ensure the collection exists.

        Returns True if a collection was created in this call. Existing data is
        never dropped unless `recreate=True` is explicitly requested.
        """

        exists = bool(self.client.has_collection(collection_name=self.collection_name))
        if exists and recreate:
            self.client.drop_collection(collection_name=self.collection_name)
            exists = False

        if exists:
            describe = getattr(self.client, "describe_collection", None)
            if callable(describe):
                dimension = _extract_dimension(
                    describe(collection_name=self.collection_name)
                )
                if dimension is not None and dimension != self.manifest.dimension:
                    raise ValueError(
                        "existing Milvus collection dimension does not match embeddings: "
                        f"{dimension} != {self.manifest.dimension}. "
                        "Use a new collection name or --recreate only after confirming data safety."
                    )
            return False

        _, DataType = _import_pymilvus()
        schema = self.client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field(
            field_name="chunk_id",
            datatype=DataType.VARCHAR,
            max_length=512,
            is_primary=True,
        )
        schema.add_field(
            field_name=MILVUS_VECTOR_FIELD,
            datatype=DataType.FLOAT_VECTOR,
            dim=self.manifest.dimension,
        )
        schema.add_field(field_name="document_id", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="source_file", datatype=DataType.VARCHAR, max_length=1024)
        schema.add_field(field_name="content_type", datatype=DataType.VARCHAR, max_length=32)
        schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=4096)
        schema.add_field(
            field_name="section_path_json", datatype=DataType.VARCHAR, max_length=16384
        )
        schema.add_field(field_name="page_start", datatype=DataType.INT64)
        schema.add_field(field_name="page_end", datatype=DataType.INT64)
        schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(
            field_name="embedding_text", datatype=DataType.VARCHAR, max_length=65535
        )
        schema.add_field(field_name="table_title", datatype=DataType.VARCHAR, max_length=4096)
        schema.add_field(field_name="table_no", datatype=DataType.INT64)
        schema.add_field(
            field_name="metadata_json", datatype=DataType.VARCHAR, max_length=32768
        )
        schema.add_field(
            field_name="embedding_model", datatype=DataType.VARCHAR, max_length=512
        )
        schema.add_field(field_name="embedding_normalized", datatype=DataType.BOOL)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name=MILVUS_VECTOR_FIELD,
            index_type="AUTOINDEX",
            metric_type=MILVUS_METRIC_TYPE,
        )
        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        return True

    def upsert(
        self,
        *,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
        batch_size: int = 100,
        recreate: bool = False,
    ) -> MilvusIngestSummary:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if len(chunks) != self.manifest.chunk_count:
            raise ValueError(
                f"manifest expects {self.manifest.chunk_count} chunks, got {len(chunks)}"
            )

        created = self.ensure_collection(recreate=recreate)
        records = list(iter_milvus_records(chunks, embeddings, self.manifest))

        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            self.client.upsert(collection_name=self.collection_name, data=batch)

        # This is idempotent on supported MilvusClient deployments and makes
        # search readiness explicit for an already-existing collection.
        load_collection = getattr(self.client, "load_collection", None)
        if callable(load_collection):
            load_collection(collection_name=self.collection_name)

        return MilvusIngestSummary(
            uri=self.uri,
            collection_name=self.collection_name,
            chunk_count=len(records),
            dimension=self.manifest.dimension,
            model_name=self.manifest.model_name,
            normalized=self.manifest.normalized,
            batch_size=batch_size,
            operation="create+upsert" if created else "upsert",
        )

    def search(
        self,
        query: str,
        *,
        embedder: TextEmbedder,
        top_k: int = 5,
        filter_expr: str | None = None,
    ) -> DenseSearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if embedder.model_name != self.manifest.model_name:
            raise ValueError(
                "query model does not match Milvus collection embeddings: "
                f"{embedder.model_name!r} != {self.manifest.model_name!r}"
            )
        if embedder.dimension != self.manifest.dimension:
            raise ValueError(
                "query embedding dimension does not match Milvus collection: "
                f"{embedder.dimension} != {self.manifest.dimension}"
            )

        query_vector = np.asarray(embedder.encode_query(query), dtype=np.float32)
        if query_vector.shape != (self.manifest.dimension,):
            raise ValueError(
                f"expected query vector shape {(self.manifest.dimension,)}, got {query_vector.shape}"
            )
        if not np.isfinite(query_vector).all():
            raise ValueError("query vector contains NaN or infinity")
        if self.manifest.normalized:
            norm = float(np.linalg.norm(query_vector))
            if norm <= 0:
                raise ValueError("query vector has zero norm")
            query_vector = query_vector / norm

        load_collection = getattr(self.client, "load_collection", None)
        if callable(load_collection):
            load_collection(collection_name=self.collection_name)

        kwargs: dict[str, Any] = {
            "collection_name": self.collection_name,
            "data": [query_vector.tolist()],
            "anns_field": MILVUS_VECTOR_FIELD,
            "limit": top_k,
            "output_fields": _OUTPUT_FIELDS,
            "search_params": {"metric_type": MILVUS_METRIC_TYPE, "params": {}},
        }
        if filter_expr:
            kwargs["filter"] = filter_expr
        raw = self.client.search(**kwargs)
        rows = raw[0] if raw else []

        hits: list[DenseSearchHit] = []
        for rank, item in enumerate(rows, start=1):
            entity = item.get("entity") or {}
            chunk_id = str(entity.get("chunk_id") or item.get("id") or "")
            if not chunk_id:
                raise ValueError("Milvus search result is missing chunk_id")
            section_path_raw = entity.get("section_path_json") or "[]"
            try:
                section_path = json.loads(section_path_raw)
                if not isinstance(section_path, list):
                    section_path = []
            except (TypeError, json.JSONDecodeError):
                section_path = []

            score = item.get("distance")
            if score is None:
                score = item.get("score", 0.0)
            table_no_raw = int(entity.get("table_no", -1))
            hits.append(
                DenseSearchHit(
                    rank=rank,
                    score=round(float(score), 6),
                    chunk_id=chunk_id,
                    document_id=str(entity.get("document_id", "")),
                    source_file=str(entity.get("source_file", "")),
                    content_type=str(entity.get("content_type", "narrative")),
                    section=str(entity.get("section") or "") or None,
                    section_path=[str(value) for value in section_path],
                    page_start=int(entity.get("page_start", 0)),
                    page_end=int(entity.get("page_end", 0)),
                    text=str(entity.get("text", "")),
                    table_title=str(entity.get("table_title") or "") or None,
                    table_no=None if table_no_raw < 0 else table_no_raw,
                )
            )

        return DenseSearchResponse(
            query=query,
            model_name=self.manifest.model_name,
            top_k=top_k,
            hits=hits,
        )


def compare_dense_rankings(
    local: DenseSearchResponse,
    milvus: DenseSearchResponse,
) -> dict[str, Any]:
    """Compare two dense backends without pretending ANN ties must be identical."""

    local_ids = [hit.chunk_id for hit in local.hits]
    milvus_ids = [hit.chunk_id for hit in milvus.hits]
    limit = min(len(local_ids), len(milvus_ids))
    local_set = set(local_ids[:limit])
    milvus_set = set(milvus_ids[:limit])
    overlap = len(local_set & milvus_set)
    same_rank = sum(
        1 for left, right in zip(local_ids[:limit], milvus_ids[:limit], strict=True) if left == right
    )
    first_mismatch = next(
        (
            index
            for index, (left, right) in enumerate(
                zip(local_ids[:limit], milvus_ids[:limit], strict=True), start=1
            )
            if left != right
        ),
        None,
    )
    return {
        "compared_k": limit,
        "overlap_count": overlap,
        "overlap_ratio": round(overlap / limit, 6) if limit else 1.0,
        "same_rank_count": same_rank,
        "same_rank_ratio": round(same_rank / limit, 6) if limit else 1.0,
        "first_rank_mismatch": first_mismatch,
        "local_chunk_ids": local_ids[:limit],
        "milvus_chunk_ids": milvus_ids[:limit],
    }
