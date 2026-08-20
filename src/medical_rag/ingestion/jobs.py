from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from medical_rag.core.config import get_settings
from medical_rag.core.paths import PROJECT_ROOT, project_path
from medical_rag.ingestion.registry import KnowledgeRegistry
from medical_rag.rag.runtime import reset_pipeline

_JOB_LOCK = threading.Lock()


def _run_command(args: list[str]) -> None:
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise RuntimeError(tail or f"command failed with exit code {result.returncode}")


def process_document_job(document_id: str) -> None:
    """Process one uploaded PDF asynchronously in an isolated Python process.

    The local product serializes ingestion jobs deliberately. It avoids loading
    multiple MPS embedding models at once and mirrors the job boundary that a
    production task queue would provide.
    """

    registry = KnowledgeRegistry()
    with _JOB_LOCK:
        record = registry.get(document_id)
        if record is None:
            return
        source = project_path(record.source_path)
        output_dir = project_path(record.processed_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            registry.update(
                document_id,
                status="parsing",
                progress=15,
                stage_message="正在解析 PDF、清洗正文并识别表格",
                error=None,
            )
            _run_command(
                [
                    sys.executable,
                    "scripts/parse_pdf.py",
                    str(source),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            registry.update(
                document_id,
                status="chunking",
                progress=45,
                stage_message="正在按章节、段落和表格生成知识片段",
            )
            _run_command(
                [
                    sys.executable,
                    "scripts/chunk_document.py",
                    str(output_dir / "cleaned_document.json"),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            registry.update(
                document_id,
                status="embedding",
                progress=70,
                stage_message="正在生成语义向量",
            )
            settings = get_settings()
            device = settings.rag_embedding_device or "auto"
            _run_command(
                [
                    sys.executable,
                    "scripts/embed_chunks.py",
                    str(output_dir / "chunks.json"),
                    "--output-dir",
                    str(output_dir),
                    "--model",
                    settings.rag_embedding_model,
                    "--device",
                    device,
                    "--batch-size",
                    str(settings.rag_embedding_batch_size),
                ]
            )

            registry.update(
                document_id,
                status="indexing",
                progress=92,
                stage_message="正在发布到当前可检索知识库",
            )
            chunk_report = json.loads(
                (output_dir / "chunk_report.json").read_text(encoding="utf-8")
            )
            chunk_count = int(chunk_report.get("chunk_count", 0))

            # The local query service builds an aggregate exact index lazily from
            # all ready documents. Marking the record ready is the publish step.
            registry.update(
                document_id,
                status="ready",
                progress=100,
                stage_message="处理完成，已进入可检索知识库",
                chunk_count=chunk_count,
                error=None,
            )
            reset_pipeline()
        except Exception as exc:
            registry.update(
                document_id,
                status="failed",
                progress=100,
                stage_message="处理失败，可查看错误后重新处理",
                error=str(exc),
            )


__all__ = ["process_document_job"]
