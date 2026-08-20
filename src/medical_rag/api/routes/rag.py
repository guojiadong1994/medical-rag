from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from medical_rag.auth.service import require_access_token
from medical_rag.generation.client import LLMGenerationError
from medical_rag.rag.pipeline import RAGPipelineConfigurationError, RAGRequest
from medical_rag.rag.runtime import get_pipeline, get_runtime_status

router = APIRouter(
    prefix="/api/v1/rag",
    tags=["rag"],
    dependencies=[Depends(require_access_token)],
)

assistant_router = APIRouter(
    prefix="/api/v1/me/assistant",
    tags=["assistant"],
    dependencies=[Depends(require_access_token)],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    patientId: str | None = None


async def _run_question(payload: AskRequest) -> dict:
    try:
        pipeline = get_pipeline()
        result = await pipeline.run(
            RAGRequest(query=payload.question, patient_id=payload.patientId)
        )
        return result.model_dump()
    except RAGPipelineConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"知识检索服务尚未就绪：{exc}",
        ) from exc
    except LLMGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"大模型服务调用失败：{exc}",
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"知识库运行文件缺失：{exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"知识检索运行失败：{exc}",
        ) from exc


@router.post("/ask")
async def ask(payload: AskRequest) -> dict:
    return await _run_question(payload)


@router.get("/status")
async def rag_status() -> dict:
    runtime = get_runtime_status()
    return {
        "loaded": runtime.loaded,
        "loading": runtime.loading,
        "error": runtime.error,
    }


# Alias for the current Vue front-end product structure. It returns the same
# payload as /api/v1/rag/ask, so the front end can migrate without duplicating
# business logic.
@assistant_router.post("/chat")
async def assistant_chat(payload: AskRequest) -> dict:
    return await _run_question(payload)
