from pathlib import Path
from typing import Protocol


class ParsedDocument(dict):
    pass


class DocumentParser(Protocol):
    async def parse(self, path: Path) -> ParsedDocument:
        ...
