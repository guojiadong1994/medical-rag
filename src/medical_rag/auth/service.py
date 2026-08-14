from secrets import compare_digest

from fastapi import Header, HTTPException, status

from medical_rag.core.config import get_settings


def verify_credentials(username: str, password: str) -> bool:
    settings = get_settings()
    return compare_digest(username, settings.doctor_username) and compare_digest(
        password, settings.doctor_password
    )


def require_access_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.access_token}"
    if authorization is None or not compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效，请重新登录",
        )
