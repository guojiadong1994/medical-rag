from __future__ import annotations

from secrets import compare_digest

from fastapi import Header, HTTPException, status

from medical_rag.core.config import get_settings


PRESET_USERS: dict[str, dict[str, str]] = {
    "user001": {
        "password": "123456",
        "id": "U10001",
        "name": "郭嘉栋",
        "role": "user",
        "account": "user001",
    },
    "admin": {
        "password": "admin123",
        "id": "A10001",
        "name": "系统管理员",
        "role": "admin",
        "account": "admin",
    },
}


def authenticate_user(username: str, password: str) -> dict[str, str] | None:
    """Authenticate the restored product accounts and the legacy doctor account.

    The two product accounts match the original Vue front-end design. The legacy
    ``doctor`` account is retained so existing scripts/tests do not break.
    """

    preset = PRESET_USERS.get(username)
    if preset and compare_digest(password, preset["password"]):
        return {key: value for key, value in preset.items() if key != "password"}

    settings = get_settings()
    if compare_digest(username, settings.doctor_username) and compare_digest(
        password, settings.doctor_password
    ):
        return {
            "id": "D001",
            "name": "王医生",
            "role": "user",
            "account": settings.doctor_username,
        }
    return None


def verify_credentials(username: str, password: str) -> bool:
    """Backward-compatible boolean credential check."""

    return authenticate_user(username, password) is not None


def require_access_token(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.access_token}"
    if authorization is None or not compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效，请重新登录",
        )
