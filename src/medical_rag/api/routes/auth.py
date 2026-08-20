from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from medical_rag.auth.service import authenticate_user
from medical_rag.core.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
async def login(payload: LoginRequest) -> dict:
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    settings = get_settings()
    return {
        "accessToken": settings.access_token,
        "user": user,
        # Keep the old field for compatibility with the early backend-only client.
        "doctor": {
            "id": user["id"],
            "name": user["name"],
            "department": "综合保障医学中心",
            "title": "用户" if user["role"] == "user" else "平台管理员",
        },
    }
