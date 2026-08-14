from pathlib import Path
from typing import Protocol

from medical_rag.parsing.models import ParsedDocument


class DocumentParser(Protocol):
    async def parse(self, path: Path) -> ParsedDocument:
        ...
