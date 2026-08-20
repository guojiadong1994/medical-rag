from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from medical_rag.core.paths import project_path

KnowledgeStatus = Literal[
    "uploaded",
    "parsing",
    "chunking",
    "embedding",
    "indexing",
    "ready",
    "failed",
]

_STATUS_LABELS: dict[str, str] = {
    "uploaded": "已上传",
    "parsing": "正在解析",
    "chunking": "正在分块",
    "embedding": "正在向量化",
    "indexing": "正在建立索引",
    "ready": "已索引",
    "failed": "处理失败",
}


class KnowledgeDocumentRecord(BaseModel):
    id: str
    name: str
    category: str = "未分类"
    file_type: str = "PDF"
    size_bytes: int = 0
    uploaded_at: str
    updated_at: str
    status: KnowledgeStatus = "uploaded"
    progress: int = Field(default=0, ge=0, le=100)
    stage_message: str = "等待处理"
    chunk_count: int = 0
    error: str | None = None
    source_path: str
    processed_dir: str

    @property
    def status_label(self) -> str:
        return _STATUS_LABELS.get(self.status, self.status)

    def api_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "fileType": self.file_type,
            "sizeText": _size_text(self.size_bytes),
            "uploadedAt": self.uploaded_at,
            "updatedAt": self.updated_at,
            "status": self.status_label,
            "statusCode": self.status,
            "progress": self.progress,
            "stageMessage": self.stage_message,
            "chunks": self.chunk_count,
            "error": self.error,
        }


def _size_text(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class KnowledgeRegistry:
    """Tiny persistent registry for the single-node product build.

    Production deployments normally put these records in PostgreSQL and use a
    dedicated task queue. Keeping the registry as JSON here lets the local
    product run without introducing another mandatory service while preserving
    the same document/job state model.
    """

    _lock = threading.RLock()

    def __init__(self, path: str | Path = "data/knowledge/registry.json") -> None:
        self.path = project_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[KnowledgeDocumentRecord]:
        with self._lock:
            return self._load()

    def get(self, document_id: str) -> KnowledgeDocumentRecord | None:
        return next((item for item in self.list() if item.id == document_id), None)

    def upsert(self, record: KnowledgeDocumentRecord) -> KnowledgeDocumentRecord:
        with self._lock:
            items = self._load()
            for index, current in enumerate(items):
                if current.id == record.id:
                    items[index] = record
                    break
            else:
                items.append(record)
            self._save(items)
        return record

    def update(self, document_id: str, **changes: object) -> KnowledgeDocumentRecord:
        with self._lock:
            items = self._load()
            for index, current in enumerate(items):
                if current.id != document_id:
                    continue
                payload = current.model_dump()
                payload.update(changes)
                payload["updated_at"] = now_text()
                updated = KnowledgeDocumentRecord.model_validate(payload)
                items[index] = updated
                self._save(items)
                return updated
        raise KeyError(document_id)

    def _load(self) -> list[KnowledgeDocumentRecord]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        return [KnowledgeDocumentRecord.model_validate(item) for item in payload]

    def _save(self, items: list[KnowledgeDocumentRecord]) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps([item.model_dump() for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)


__all__ = ["KnowledgeDocumentRecord", "KnowledgeRegistry", "KnowledgeStatus", "now_text"]
