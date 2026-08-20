from __future__ import annotations

import argparse
import json

from medical_rag.rag.pipeline import RAGRequest
from medical_rag.rag.runtime import get_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one Product V1 medical RAG question")
    parser.add_argument("question")
    parser.add_argument("--patient-id", default=None)
    args = parser.parse_args()

    result = get_pipeline().ask(
        RAGRequest(query=args.question, patient_id=args.patient_id)
    )
    print(result.answer)
    print("\n--- 来源 ---")
    for source in result.sources:
        marker = "*" if source.used_in_answer else "-"
        page = (
            str(source.page_start)
            if source.page_start == source.page_end
            else f"{source.page_start}-{source.page_end}"
        )
        print(f"{marker} [{source.citation_id}] {source.source_file} P{page} {source.section or ''}")
    print("\n--- 运行诊断 ---")
    print(json.dumps(result.diagnostics.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
