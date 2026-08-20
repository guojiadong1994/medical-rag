from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding.io import (
    load_chunks,
    load_embedding_matrix,
    load_manifest,
    validate_chunks_against_manifest,
)
from medical_rag.retrieval import (
    DEFAULT_MILVUS_COLLECTION,
    DEFAULT_MILVUS_URI,
    MilvusDenseIndex,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(
    chunks_path: Path,
    embeddings_path: Path,
    manifest_path: Path,
    *,
    uri: str,
    token: str | None,
    collection_name: str,
    batch_size: int,
    recreate: bool,
    output_dir: Path,
) -> None:
    chunks = load_chunks(chunks_path)
    manifest = load_manifest(manifest_path)
    validate_chunks_against_manifest(chunks, manifest)
    embeddings = load_embedding_matrix(embeddings_path, manifest)

    index = MilvusDenseIndex(
        uri=uri,
        token=token,
        collection_name=collection_name,
        manifest=manifest,
    )
    summary = index.upsert(
        chunks=chunks,
        embeddings=embeddings,
        batch_size=batch_size,
        recreate=recreate,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "milvus_ingest_report.json"
    _write_json(report_path, summary.as_dict())

    print(json.dumps(summary.as_dict(), ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {report_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upsert existing chunk embeddings into Milvus without recomputing vectors"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--uri", default=DEFAULT_MILVUS_URI)
    parser.add_argument("--token", default=None)
    parser.add_argument("--collection", default=DEFAULT_MILVUS_COLLECTION)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help=(
            "DROP the existing collection before ingestion. This is destructive and is never "
            "enabled by default."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    run(
        args.chunks_json,
        args.embeddings or parent / "embeddings.npy",
        args.manifest or parent / "embedding_manifest.json",
        uri=args.uri,
        token=args.token,
        collection_name=args.collection,
        batch_size=args.batch_size,
        recreate=args.recreate,
        output_dir=args.output_dir or parent,
    )


if __name__ == "__main__":
    main()
