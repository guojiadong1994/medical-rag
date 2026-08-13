from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from medical_rag.auth.service import verify_credentials
from medical_rag.core.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    settings = get_settings()
    return {
        "accessToken": settings.access_token,
        "doctor": {
            "id": "D001",
            "name": "王医生",
            "department": "综合保障医学中心",
            "title": "主治医师",
        },
    }
