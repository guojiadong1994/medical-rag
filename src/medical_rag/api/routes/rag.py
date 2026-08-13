from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from medical_rag.auth.service import require_access_token

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["rag"],
    dependencies=[Depends(require_access_token)],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    patientId: str | None = None


@router.post("/ask")
async def ask(_: AskRequest) -> dict:
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="知识检索服务暂不可用")
