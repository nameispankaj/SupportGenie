from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    text: str


class KnowledgeBase:
    """Loads local approved files. Files are evidence, not executable instructions."""
    SUPPORTED = {".txt", ".md", ".pdf", ".docx"}

    def __init__(self, folder: Path, chunk_chars: int = 3500):
        self.folder = folder
        self.chunk_chars = chunk_chars

    def load(self) -> list[KnowledgeChunk]:
        self.folder.mkdir(parents=True, exist_ok=True)
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in self.SUPPORTED:
                continue
            try:
                text = self._extract(path)
            except Exception:
                continue
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if not text:
                continue
            for index, part in enumerate(self._chunk(text), start=1):
                chunks.append(KnowledgeChunk(source=f"{path.name} (chunk {index})", text=part))
        return chunks

    def _extract(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        return ""

    def _chunk(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        chunks, current = [], ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 1 > self.chunk_chars:
                chunks.append(current)
                current = ""
            current = f"{current}\n{paragraph}".strip()
        if current:
            chunks.append(current)
        return chunks
