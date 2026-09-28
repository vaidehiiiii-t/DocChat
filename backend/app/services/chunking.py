from dataclasses import dataclass
from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass
class ChunkData:
    chunk_index: int
    page_number: int
    text: str
    char_count: int
    token_count: int


class ChunkingService:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150, min_chunk_chars: int = 20):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_chars = min_chunk_chars
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )

    def chunk_pages(self, pages: Sequence[tuple[int, str]]) -> list[ChunkData]:
        """
        Split text page-by-page, preserving page numbers and assigning contiguous global chunk indices.
        Filters out noise/empty chunks with fewer than min_chunk_chars characters.
        """
        chunks: list[ChunkData] = []
        global_index = 0

        for page_num, page_text in pages:
            if not page_text or not page_text.strip():
                continue

            page_splits = self.splitter.split_text(page_text)
            for split_text in page_splits:
                cleaned = split_text.strip()
                if len(cleaned) < self.min_chunk_chars:
                    continue

                chunk = ChunkData(
                    chunk_index=global_index,
                    page_number=page_num,
                    text=cleaned,
                    char_count=len(cleaned),
                    token_count=max(1, len(cleaned) // 4),
                )
                chunks.append(chunk)
                global_index += 1

        return chunks
