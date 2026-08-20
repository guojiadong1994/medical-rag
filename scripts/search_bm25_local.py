from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.retrieval import LocalBM25Index


def main() -> None:
    parser = argparse.ArgumentParser(description="Local BM25 sparse retrieval")
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--k1", type=float, default=1.5)
    parser.add_argument("--b", type=float, default=0.75)
    args = parser.parse_args()

    index = LocalBM25Index.load(args.chunks_json, k1=args.k1, b=args.b)
    response = index.search(args.query, top_k=args.top_k)

    print(f"Query: {response.query}")
    print(f"Tokenizer: {response.tokenizer_name}\n")
    for hit in response.hits:
        section = hit.section or "—"
        preview = hit.text[:320].replace("\n", " ")
        print(
            f"#{hit.rank}  score={hit.score:.6f}  "
            f"page={hit.page_start}-{hit.page_end}  type={hit.content_type}"
        )
        print(f"section={section}")
        print(preview)
        print()

    parent = args.chunks_json.parent
    output = parent / "bm25_search_results.json"
    output.write_text(
        json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Artifact written to: {output.resolve()}")


if __name__ == "__main__":
    main()
