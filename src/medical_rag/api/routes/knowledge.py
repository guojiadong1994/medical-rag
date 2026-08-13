from datetime import datetime
from hashlib import sha1
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from medical_rag.auth.service import require_access_token

router = APIRouter(
    prefix="/api/v1/knowledge",
    tags=["knowledge"],
    dependencies=[Depends(require_access_token)],
)

KNOWLEDGE_DIR = Path("data/knowledge/inbox")


def _size_text(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _record(path: Path) -> dict:
    stat = path.stat()
    key = f"{path.name}:{stat.st_mtime_ns}".encode("utf-8")
    return {
        "id": sha1(key).hexdigest()[:16],
        "name": path.name,
        "category": "未分类",
        "fileType": path.suffix.lstrip(".").upper() or "FILE",
        "sizeText": _size_text(stat.st_size),
        "uploadedAt": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "status": "已上传",
    }


@router.get("/documents")
async def list_documents() -> list[dict]:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    return [_record(path) for path in sorted(KNOWLEDGE_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)]


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文档")

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    target = KNOWLEDGE_DIR / filename
    content = await file.read()
    target.write_bytes(content)
    return _record(target)
