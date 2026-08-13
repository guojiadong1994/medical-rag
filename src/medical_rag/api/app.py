from fastapi import FastAPI

from medical_rag.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="medical-rag",
    version="0.1.0",
    description="Patient-Centric Multimodal Medical RAG",
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/api/v1/system/info", tags=["system"])
async def system_info() -> dict:
    return {
        "project": "JD 特定人群生理孪生与医疗保障大模型平台",
        "module": "多源图文医疗知识增强检索子系统",
        "phase": "Phase 0",
        "version": "0.1.0",
    }
