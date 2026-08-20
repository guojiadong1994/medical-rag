from __future__ import annotations

import uvicorn

from medical_rag.core.config import get_settings


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "medical_rag.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
