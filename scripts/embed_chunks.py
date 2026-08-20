from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import mean

import numpy as np

from medical_rag.embedding import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingManifest,
    EmbeddingReport,
    SentenceTransformerEmbedder,
)
from medical_rag.embedding.io import build_refs, load_chunks


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(
    chunks_path: Path,
    output_dir: Path,
    *,
    model_name: str,
    device: str | None,
    batch_size: int,
    max_seq_length: int | None,
) -> None:
    chunks = load_chunks(chunks_path)
    if not chunks:
        raise ValueError("chunks.json contains no chunks")

    document_ids = {chunk.document_id for chunk in chunks}
    source_files = {chunk.source_file for chunk in chunks}
    if len(document_ids) != 1 or len(source_files) != 1:
        raise ValueError("Embedding V1 expects chunks from exactly one source document")

    empty_count = sum(1 for chunk in chunks if not chunk.embedding_text.strip())
    if empty_count:
        raise ValueError(f"found {empty_count} chunks with empty embedding_text")

    print(f"Loading embedding model: {model_name}")
    embedder = SentenceTransformerEmbedder(
        model_name,
        device=device,
        batch_size=batch_size,
        normalize_embeddings=True,
        max_seq_length=max_seq_length,
        show_progress_bar=True,
    )
    print(f"Device: {embedder.device}")
    print(f"Dimension: {embedder.dimension}")
    print(f"Chunks: {len(chunks)}")

    started = time.perf_counter()
    matrix = embedder.encode_documents([chunk.embedding_text for chunk in chunks])
    elapsed = time.perf_counter() - started

    if matrix.shape != (len(chunks), embedder.dimension):
        raise ValueError(f"unexpected embedding matrix shape: {matrix.shape}")
    finite = bool(np.isfinite(matrix).all())
    if not finite:
        raise ValueError("embedding matrix contains NaN or infinity")

    norms = np.linalg.norm(matrix, axis=1)
    output_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = output_dir / "embeddings.npy"
    manifest_path = output_dir / "embedding_manifest.json"
    report_path = output_dir / "embedding_report.json"

    np.save(embeddings_path, np.ascontiguousarray(matrix, dtype=np.float32), allow_pickle=False)

    manifest = EmbeddingManifest(
        document_id=next(iter(document_ids)),
        source_file=next(iter(source_files)),
        model_name=embedder.model_name,
        dimension=embedder.dimension,
        normalized=True,
        dtype="float32",
        chunk_count=len(chunks),
        refs=build_refs(chunks),
    )
    _write_json(manifest_path, manifest.model_dump(mode="json"))

    report = EmbeddingReport(
        document_id=manifest.document_id,
        source_file=manifest.source_file,
        model_name=manifest.model_name,
        device=embedder.device,
        chunk_count=len(chunks),
        dimension=embedder.dimension,
        normalized=True,
        dtype="float32",
        finite=finite,
        empty_embedding_text_count=empty_count,
        norm_min=round(float(norms.min()), 6),
        norm_mean=round(float(mean(float(value) for value in norms)), 6),
        norm_max=round(float(norms.max()), 6),
        elapsed_seconds=round(elapsed, 3),
        batch_size=batch_size,
        max_seq_length=max_seq_length,
    )
    _write_json(report_path, report.model_dump(mode="json"))

    print("\n" + json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {embeddings_path.name}")
    print(f"- {manifest_path.name}")
    print(f"- {report_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate normalized dense embeddings for chunks.json"
    )
    parser.add_argument("chunks_json", type=Path, help="Path to chunks.json")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to chunks.json parent directory",
    )
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument(
        "--device",
        default="auto",
        help="auto, cpu, mps, cuda, ...; auto lets SentenceTransformers choose",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=2048,
        help="Tokenizer/model truncation limit for this local validation stage",
    )
    args = parser.parse_args()

    run(
        args.chunks_json,
        args.output_dir or args.chunks_json.parent,
        model_name=args.model,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
    )


if __name__ == "__main__":
    main()
