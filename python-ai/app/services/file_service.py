from pathlib import Path
from typing import List

from app.core.logging_config import logger


def read_text_file(source_path: str) -> str:
    path = Path(source_path)
    logger.info("read_text_file source_path=%s", source_path)

    if not path.exists():
        raise FileNotFoundError(f"file not found: {source_path}")

    ext = path.suffix.lower()
    if ext not in [".txt", ".md"]:
        raise ValueError(f"unsupported file type: {ext}")

    text = path.read_text(encoding="utf-8")
    logger.info("read_text_file done source_path=%s text_len=%s", source_path, len(text))
    return text


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("chunk_size must be greater than overlap")

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    logger.info(
        "chunk_text done text_len=%s chunk_size=%s overlap=%s chunk_count=%s",
        len(text),
        chunk_size,
        overlap,
        len(chunks),
    )
    return chunks
