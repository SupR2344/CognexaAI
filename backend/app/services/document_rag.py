"""Autonomous Document Retrieval-Augmented Generation (RAG) Service for Cognexa AI.

Provides production-grade, page-aware semantic chunking, dense vector indexing,
hybrid retrieval (cosine similarity + lexical BM25 scoring), and citation synthesis
for multi-page PDFs, technical documents, and question papers.
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.services.embedding import get_embedding, get_embeddings

logger = logging.getLogger(__name__)

INDEX_CACHE_DIR = Path("uploads/rag_indices").resolve()
INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class DocumentChunk:
    """Represents an atomic, page-anchored text segment from an ingested document."""

    def __init__(
        self,
        chunk_id: str,
        file_id: str,
        filename: str,
        page_num: int,
        text: str,
        embedding: Optional[List[float]] = None,
    ):
        self.chunk_id = chunk_id
        self.file_id = file_id
        self.filename = filename
        self.page_num = page_num
        self.text = text
        self.embedding = embedding or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "file_id": self.file_id,
            "filename": self.filename,
            "page_num": self.page_num,
            "text": self.text,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DocumentChunk:
        return cls(
            chunk_id=data["chunk_id"],
            file_id=data["file_id"],
            filename=data["filename"],
            page_num=data.get("page_num", 1),
            text=data["text"],
            embedding=data.get("embedding", []),
        )


class DocumentRAGService:
    """Manages document chunking, vector indexing, and hybrid semantic retrieval."""

    def __init__(self) -> None:
        # In-memory index cache: file_id -> List[DocumentChunk]
        self._indices: Dict[str, List[DocumentChunk]] = {}
        self._load_persisted_indices()

    def _load_persisted_indices(self) -> None:
        """Load any pre-computed document indices from disk cache on startup."""
        try:
            for file_path in INDEX_CACHE_DIR.glob("*_index.json"):
                file_id = file_path.stem.replace("_index", "")
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_chunks = json.load(f)
                    self._indices[file_id] = [DocumentChunk.from_dict(c) for c in raw_chunks]
            logger.info("RAG Service initialized with %d cached document indices.", len(self._indices))
        except Exception as exc:
            logger.warning("Could not load persisted RAG indices: %s", exc)

    def _persist_index(self, file_id: str, chunks: List[DocumentChunk]) -> None:
        """Persist indexed chunks to JSON for fast warm restarts."""
        try:
            cache_file = INDEX_CACHE_DIR / f"{file_id}_index.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in chunks], f)
        except Exception as exc:
            logger.warning("Failed to persist RAG index for %s: %s", file_id, exc)

    def chunk_document(
        self,
        file_id: str,
        filename: str,
        raw_text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 80,
    ) -> List[DocumentChunk]:
        """Split document text into semantically cohesive, page-referenced chunks.

        Handles:
        - Page headers (e.g., '--- Page X ---')
        - Numbered question boundaries (e.g., '1. ', '2. ')
        - Sliding window overlap to prevent split context loss
        """
        chunks: List[DocumentChunk] = []
        if not raw_text or not raw_text.strip():
            return chunks

        # 1. Parse pages if page separators exist
        page_blocks = re.split(r"---\s*Page\s*(\d+)\s*---", raw_text, flags=re.IGNORECASE)
        page_entries: List[Tuple[int, str]] = []

        if len(page_blocks) > 1:
            # First element might be preamble before Page 1
            if page_blocks[0].strip():
                page_entries.append((1, page_blocks[0].strip()))
            for i in range(1, len(page_blocks), 2):
                p_num = int(page_blocks[i])
                p_text = page_blocks[i + 1].strip() if i + 1 < len(page_blocks) else ""
                if p_text:
                    page_entries.append((p_num, p_text))
        else:
            page_entries.append((1, raw_text.strip()))

        chunk_counter = 0

        # 2. Chunk each page
        for page_num, text_body in page_entries:
            # Check if text contains numbered questions / distinct items
            questions = re.split(r"(?=(?:^|\n)\s*\d+[\.\)]\s+[A-Z])", text_body)
            items_to_chunk = [q.strip() for q in questions if q.strip()]

            if len(items_to_chunk) >= 2:
                # Structure-aware chunking: keep question and sub-points together
                for item in items_to_chunk:
                    if len(item) <= chunk_size * 1.5:
                        chunk_counter += 1
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{file_id}_{chunk_counter}",
                                file_id=file_id,
                                filename=filename,
                                page_num=page_num,
                                text=item,
                            )
                        )
                    else:
                        # Large block: sliding window
                        sub_chunks = self._sliding_window_split(item, chunk_size, chunk_overlap)
                        for sc in sub_chunks:
                            chunk_counter += 1
                            chunks.append(
                                DocumentChunk(
                                    chunk_id=f"{file_id}_{chunk_counter}",
                                    file_id=file_id,
                                    filename=filename,
                                    page_num=page_num,
                                    text=sc,
                                )
                            )
            else:
                # Standard paragraph / sliding window chunking
                sub_chunks = self._sliding_window_split(text_body, chunk_size, chunk_overlap)
                for sc in sub_chunks:
                    chunk_counter += 1
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{file_id}_{chunk_counter}",
                            file_id=file_id,
                            filename=filename,
                            page_num=page_num,
                            text=sc,
                        )
                    )

        return chunks

    def _sliding_window_split(self, text: str, size: int, overlap: int) -> List[str]:
        """Split arbitrary text using word-preserving sliding window."""
        words = text.split()
        if not words:
            return []
        
        words_per_chunk = max(30, size // 6)
        overlap_words = max(5, overlap // 6)
        step = max(1, words_per_chunk - overlap_words)

        results = []
        for i in range(0, len(words), step):
            window = words[i : i + words_per_chunk]
            if window:
                results.append(" ".join(window))
            if i + words_per_chunk >= len(words):
                break
        return results

    def index_document(self, file_id: str, filename: str, raw_text: str) -> int:
        """Build and cache semantic vector embeddings for all document chunks.

        Returns total indexed chunk count.
        """
        chunks = self.chunk_document(file_id, filename, raw_text)
        if not chunks:
            logger.warning("No text chunks generated for %s (%s)", filename, file_id)
            return 0

        # Compute dense embeddings in batch
        texts = [c.text for c in chunks]
        embeddings = get_embeddings(texts)

        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb

        self._indices[file_id] = chunks
        self._persist_index(file_id, chunks)

        logger.info(
            "Successfully indexed %d chunks for document '%s' (ID: %s)",
            len(chunks),
            filename,
            file_id,
        )
        return len(chunks)

    def retrieve_relevant_chunks(
        self,
        query: str,
        file_id: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """Execute hybrid search (cosine similarity + lexical BM25 matching).

        Args:
            query: User prompt or search question.
            file_id: Specific document ID to filter on (or None to search across all uploaded docs).
            top_k: Maximum number of relevant chunks to retrieve.
            min_score: Similarity threshold.

        Returns:
            List of scored chunk dicts with page citations and relevance metrics.
        """
        if not query or not query.strip():
            return []

        # Gather candidate pool
        pool: List[DocumentChunk] = []
        if file_id and file_id in self._indices:
            pool = self._indices[file_id]
        else:
            for c_list in self._indices.values():
                pool.extend(c_list)

        if not pool:
            return []

        query_vec = np.array(get_embedding(query), dtype=np.float32)
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec = query_vec / q_norm

        query_tokens = set(re.findall(r"\w+", query.lower()))

        scored_results: List[Tuple[float, DocumentChunk]] = []

        for chunk in pool:
            if not chunk.embedding:
                continue

            c_vec = np.array(chunk.embedding, dtype=np.float32)
            c_norm = np.linalg.norm(c_vec)
            if c_norm > 0:
                c_vec = c_vec / c_norm

            # 1. Dense Cosine Similarity
            dense_sim = float(np.dot(query_vec, c_vec))

            # 2. Lexical / Keyword Overlap (BM25 heuristic)
            chunk_tokens = set(re.findall(r"\w+", chunk.text.lower()))
            if query_tokens and chunk_tokens:
                overlap = len(query_tokens.intersection(chunk_tokens))
                lexical_score = overlap / math.sqrt(len(query_tokens) * len(chunk_tokens) + 1e-5)
            else:
                lexical_score = 0.0

            # 3. Hybrid Combined Score (70% semantic, 30% exact keyword)
            hybrid_score = (0.70 * dense_sim) + (0.30 * min(1.0, lexical_score * 2.5))

            if hybrid_score >= min_score:
                scored_results.append((hybrid_score, chunk))

        # Sort descending by score
        scored_results.sort(key=lambda x: x[0], reverse=True)

        selected = scored_results[:top_k]
        output = []
        for score, chk in selected:
            output.append({
                "score": round(score, 4),
                "page_num": chk.page_num,
                "filename": chk.filename,
                "file_id": chk.file_id,
                "chunk_id": chk.chunk_id,
                "text": chk.text,
                "citation": f"[Page {chk.page_num} of {chk.filename}]",
            })

        return output

    def build_rag_context(
        self,
        query: str,
        file_id: Optional[str] = None,
        top_k: int = 5,
    ) -> str:
        """Formulate a grounded, cited context block from retrieved document chunks."""
        chunks = self.retrieve_relevant_chunks(query, file_id=file_id, top_k=top_k)
        if not chunks:
            return ""

        context_lines = [
            f"--- 📚 RETRIEVED GROUND-TRUTH DOCUMENT CONTEXT (Top {len(chunks)} Chunks) ---"
        ]
        for idx, ch in enumerate(chunks, 1):
            context_lines.append(
                f"\n[Source Citation {idx} | {ch['citation']} | Relevance: {int(ch['score'] * 100)}%]:\n{ch['text']}"
            )
        context_lines.append("\n--- END RETRIEVED DOCUMENT CONTEXT ---")
        return "\n".join(context_lines)


# Global Singleton Service
document_rag = DocumentRAGService()
