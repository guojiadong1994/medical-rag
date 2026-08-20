from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Locate the repository root by looking for pyproject.toml.

    This avoids depending on the shell's current working directory, which is
    important when the API is started from an IDE, uvicorn, Docker, or a shell.
    """

    candidate = (start or Path(__file__)).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for path in (candidate, *candidate.parents):
        if (path / "pyproject.toml").exists():
            return path
    return Path.cwd().resolve()


PROJECT_ROOT = find_project_root()


def project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


__all__ = ["PROJECT_ROOT", "find_project_root", "project_path"]
