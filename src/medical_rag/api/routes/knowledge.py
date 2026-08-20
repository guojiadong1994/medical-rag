from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status

from medical_rag.auth.service import require_access_token
from medical_rag.core.paths import project_path
from medical_rag.ingestion.jobs import process_document_job
from medical_rag.ingestion.registry import KnowledgeDocumentRecord, KnowledgeRegistry, now_text

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_access_token)],
)

REGISTRY = KnowledgeRegistry()
LEGACY_DIR = project_path("data/processed/hypertension_2024")
LEGACY_SOURCE = project_path("data/knowledge/inbox/中国高血压防治指南(2024年修订版).pdf")


def _size_text(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _legacy_record() -> dict | None:
    chunks_path = LEGACY_DIR / "chunks.json"
    manifest_path = LEGACY_DIR / "embedding_manifest.json"
    embeddings_path = LEGACY_DIR / "embeddings.npy"
    if not (chunks_path.exists() and manifest_path.exists() and embeddings_path.exists()):
        return None

    chunk_count = 0
    report_path = LEGACY_DIR / "chunk_report.json"
    if report_path.exists():
        try:
            chunk_count = int(json.loads(report_path.read_text(encoding="utf-8")).get("chunk_count", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            chunk_count = 0
    if chunk_count <= 0:
        try:
            payload = json.loads(chunks_path.read_text(encoding="utf-8"))
            chunk_count = len(payload) if isinstance(payload, list) else 0
        except json.JSONDecodeError:
            chunk_count = 0

    source_size = LEGACY_SOURCE.stat().st_size if LEGACY_SOURCE.exists() else 0
    updated_at = max(
        path.stat().st_mtime for path in (chunks_path, manifest_path, embeddings_path)
    )
    from datetime import datetime

    return {
        "id": "legacy-hypertension-2024",
        "name": "中国高血压防治指南（2024年修订版）.pdf",
        "category": "临床指南",
        "fileType": "PDF",
        "sizeText": _size_text(source_size) if source_size else "本地知识库",
        "uploadedAt": "历史已验证知识",
        "updatedAt": datetime.fromtimestamp(updated_at).strftime("%Y-%m-%d %H:%M:%S"),
        "status": "已索引",
        "statusCode": "ready",
        "progress": 100,
        "stageMessage": "已进入当前可检索知识库",
        "chunks": chunk_count,
        "error": None,
        "legacy": True,
    }


@router.get("/documents")
async def list_documents() -> list[dict]:
    records = [item.api_dict() | {"legacy": False} for item in REGISTRY.list()]
    legacy = _legacy_record()
    if legacy:
        records.insert(0, legacy)
    return records


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form("临床指南"),
) -> dict:
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前自动入库仅支持 PDF 文档")

    existing_names = {item.name for item in REGISTRY.list()}
    if filename in existing_names:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="同名文档已经存在。当前版本请在知识库列表中使用“重新处理”，避免重复索引。",
        )

    document_id = uuid4().hex[:16]
    source_dir = project_path(Path("data/knowledge/inbox") / document_id)
    processed_dir = project_path(Path("data/processed/knowledge_documents") / document_id)
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / filename
    content = await file.read()
    target.write_bytes(content)

    now = now_text()
    record = KnowledgeDocumentRecord(
        id=document_id,
        name=filename,
        category=category.strip() or "未分类",
        file_type="PDF",
        size_bytes=len(content),
        uploaded_at=now,
        updated_at=now,
        status="uploaded",
        progress=5,
        stage_message="文件已接收，等待后台知识入库任务",
        chunk_count=0,
        error=None,
        source_path=str(target.relative_to(project_path("."))),
        processed_dir=str(processed_dir.relative_to(project_path("."))),
    )
    REGISTRY.upsert(record)
    background_tasks.add_task(process_document_job, document_id)
    return record.api_dict() | {"legacy": False}


@router.post("/documents/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(document_id: str, background_tasks: BackgroundTasks) -> dict:
    record = REGISTRY.get(document_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识文档不存在")
    REGISTRY.update(
        document_id,
        status="uploaded",
        progress=5,
        stage_message="已提交重新处理任务",
        error=None,
    )
    background_tasks.add_task(process_document_job, document_id)
    updated = REGISTRY.get(document_id)
    assert updated is not None
    return updated.api_dict() | {"legacy": False}
