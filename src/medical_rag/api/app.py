from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medical_rag.api.routes.auth import router as auth_router
from medical_rag.api.routes.knowledge import router as knowledge_router
from medical_rag.api.routes.patients import router as patients_router
from medical_rag.api.routes.rag import router as rag_router
from medical_rag.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="medical-rag",
    version="0.2.0",
    description="Patient-Centric Multimodal Medical RAG",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(knowledge_router)
app.include_router(rag_router)


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
        "version": "0.2.0",
    }
