"""Memory Service for Cognexa AI.

Manages persistent agent memories with vector storage in PostgreSQL (pgvector),
semantic search using cosine similarity, and automatic memory extraction from conversations.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.memory import Memory
from app.services.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculate cosine similarity between two float vectors in Python."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryService:
    """Service for storing, searching, and managing agent semantic memories."""

    def __init__(
        self,
        db_session: Union[AsyncSession, Session],
        embedding_service: Optional[EmbeddingService] = None,
    ) -> None:
        """Initialize MemoryService with database session and embedding service.

        Args:
            db_session: SQLAlchemy Session or AsyncSession.
            embedding_service: EmbeddingService instance (defaults to singleton).
        """
        self.db = db_session
        self.embedding_service = embedding_service or get_embedding_service()

    @property
    def is_async(self) -> bool:
        """Check if active database session is asynchronous."""
        return isinstance(self.db, AsyncSession)

    async def _execute(self, query: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a query against either sync or async database session."""
        if self.is_async:
            if params:
                return await self.db.execute(query, params)  # type: ignore[union-attr]
            return await self.db.execute(query)  # type: ignore[union-attr]
        else:
            if params:
                return self.db.execute(query, params)  # type: ignore[union-attr]
            return self.db.execute(query)  # type: ignore[union-attr]

    async def _commit(self) -> None:
        """Commit the database transaction."""
        if self.is_async:
            await self.db.commit()  # type: ignore[union-attr]
        else:
            self.db.commit()  # type: ignore[union-attr]

    async def _refresh(self, instance: Any) -> None:
        """Refresh instance state from database."""
        if self.is_async:
            await self.db.refresh(instance)  # type: ignore[union-attr]
        else:
            self.db.refresh(instance)  # type: ignore[union-attr]

    async def store_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> Memory:
        """Create and persist an embedded memory.

        Args:
            user_id: ID of the user owning the memory.
            memory_type: Type/category of memory (fact, preference, instruction, conversation).
            content: Raw memory text content.
            metadata_: Optional metadata attributes.

        Returns:
            Newly created and persisted Memory instance.
        """
        clean_content = content.strip()
        embedding = self.embedding_service.embed(clean_content)

        memory = Memory(
            user_id=user_id,
            memory_type=memory_type,
            content=clean_content,
            embedding=embedding,
            metadata_=metadata_ or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(memory)
        await self._commit()
        await self._refresh(memory)
        logger.info("Stored memory [%s] for user %s: %s", memory.id, user_id, clean_content[:60])
        return memory

    async def search_memories(
        self,
        user_id: str,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Memory]:
        """Perform semantic search using pgvector cosine similarity.

        Uses the formula:
        SELECT *, 1 - (embedding <=> query_embedding) AS similarity
        FROM memories WHERE user_id = ... ORDER BY similarity DESC LIMIT N

        Falls back to in-memory cosine comparison if pgvector operator is unavailable.

        Args:
            user_id: ID of the user.
            query: Natural language query string.
            memory_type: Optional filter by memory_type.
            limit: Maximum number of memories to return.

        Returns:
            List of matching Memory objects with similarity score attached.
        """
        query_embedding = self.embedding_service.embed(query)
        embedding_str = f"[{','.join(f'{x:.6f}' for x in query_embedding)}]"

        type_clause = " AND memory_type = :memory_type" if memory_type else ""
        sql_query = text(
            f"""
            SELECT id, user_id, memory_type, content, metadata, created_at, updated_at,
                   1 - (embedding <=> :query_embedding) AS similarity
            FROM memories
            WHERE user_id = :user_id{type_clause}
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )

        params: Dict[str, Any] = {
            "query_embedding": embedding_str,
            "user_id": user_id,
            "limit": limit,
        }
        if memory_type:
            params["memory_type"] = memory_type

        try:
            result = await self._execute(sql_query, params)
            rows = result.fetchall()

            memories: List[Memory] = []
            for row in rows:
                mem = Memory(
                    id=row.id,
                    user_id=row.user_id,
                    memory_type=row.memory_type,
                    content=row.content,
                    metadata_=row.metadata if hasattr(row, "metadata") else {},
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                mem.similarity = float(row.similarity) if row.similarity is not None else 0.0
                memories.append(mem)
            return memories

        except Exception as sql_err:
            logger.warning(
                "pgvector direct SQL search failed or not supported in current environment (%s). "
                "Falling back to ORM query with manual cosine calculation.",
                sql_err,
            )
            # Fallback for environments/databases where pgvector operator <=> is not configured
            stmt = select(Memory).where(Memory.user_id == user_id)
            if memory_type:
                stmt = stmt.where(Memory.memory_type == memory_type)

            result = await self._execute(stmt)
            all_records = result.scalars().all()

            scored: List[tuple[Memory, float]] = []
            for rec in all_records:
                if rec.embedding:
                    sim = _cosine_similarity(query_embedding, rec.embedding)
                    rec.similarity = sim
                    scored.append((rec, sim))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [item[0] for item in scored[:limit]]

    async def get_relevant_context(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> str:
        """Retrieve relevant memories formatted as context for LLM prompt injection.

        Args:
            user_id: User identifier.
            query: Query or message text.
            limit: Maximum memories to include.

        Returns:
            Formatted context string.
        """
        memories = await self.search_memories(user_id=user_id, query=query, limit=limit)
        if not memories:
            return ""

        context_lines: List[str] = ["Relevant Memories & Context:"]
        for idx, mem in enumerate(memories, 1):
            sim_str = f" (relevance: {mem.similarity:.2f})" if mem.similarity is not None else ""
            context_lines.append(f"{idx}. [{mem.memory_type.upper()}]{sim_str}: {mem.content}")

        return "\n".join(context_lines)

    async def update_memory(
        self,
        memory_id: str,
        user_id: str,
        updates: Dict[str, Any],
    ) -> Optional[Memory]:
        """Update an existing memory by ID and user ID.

        Recalculates embedding if content is updated.

        Args:
            memory_id: Target memory ID.
            user_id: User identifier owning the memory.
            updates: Dictionary of fields to update (content, memory_type, metadata_).

        Returns:
            Updated Memory instance or None if not found.
        """
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        result = await self._execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            logger.warning("Memory %s for user %s not found for update.", memory_id, user_id)
            return None

        if "content" in updates and updates["content"]:
            new_content = updates["content"].strip()
            memory.content = new_content
            memory.embedding = self.embedding_service.embed(new_content)

        if "memory_type" in updates:
            memory.memory_type = updates["memory_type"]

        if "metadata_" in updates:
            current_meta = memory.metadata_ or {}
            current_meta.update(updates["metadata_"])
            memory.metadata_ = current_meta
        elif "metadata" in updates:
            current_meta = memory.metadata_ or {}
            current_meta.update(updates["metadata"])
            memory.metadata_ = current_meta

        memory.updated_at = datetime.utcnow()
        await self._commit()
        await self._refresh(memory)
        return memory

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """Delete a memory record by ID and user ID.

        Args:
            memory_id: Memory identifier.
            user_id: User identifier.

        Returns:
            True if memory was deleted, False if record was not found.
        """
        stmt = select(Memory).where(Memory.id == memory_id, Memory.user_id == user_id)
        result = await self._execute(stmt)
        memory = result.scalar_one_or_none()
        if not memory:
            return False

        if self.is_async:
            await self.db.delete(memory)  # type: ignore[union-attr]
        else:
            self.db.delete(memory)  # type: ignore[union-attr]

        await self._commit()
        logger.info("Deleted memory %s for user %s", memory_id, user_id)
        return True

    async def list_memories(
        self,
        user_id: str,
        memory_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Memory]:
        """List memories for a user with pagination and optional type filter.

        Args:
            user_id: User identifier.
            memory_type: Optional filter by type.
            skip: Number of records to skip (offset).
            limit: Maximum records to return.

        Returns:
            List of Memory objects.
        """
        stmt = select(Memory).where(Memory.user_id == user_id)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)

        stmt = stmt.order_by(Memory.created_at.desc()).offset(skip).limit(limit)
        result = await self._execute(stmt)
        return list(result.scalars().all())

    async def extract_and_store_memories(
        self,
        user_id: str,
        conversation_text: str,
        llm_service: Any,
    ) -> List[Memory]:
        """Extract important facts, preferences, and context from conversation using LLM and persist them.

        Args:
            user_id: User identifier.
            conversation_text: Conversation log or dialog text.
            llm_service: OllamaLLMService or LLM service instance.

        Returns:
            List of newly stored Memory instances.
        """
        if not conversation_text or not conversation_text.strip():
            return []

        extraction_system_prompt = (
            "You are an AI memory extraction system. Analyze the conversation and extract key user preferences, "
            "technical stack details, project requirements, architectural decisions, and personal facts. "
            "Output ONLY valid JSON as a list of objects with keys 'memory_type' (preference, fact, project, instruction) "
            "and 'content' (concise description). Example: "
            '[{"memory_type": "preference", "content": "Prefers FastAPI over Flask"}, '
            '{"memory_type": "project", "content": "Cognexa AI uses pgvector and Ollama"}]\n'
            "If no meaningful memories are present, return []."
        )

        prompt = f"Analyze this conversation and extract durable memories:\n\n{conversation_text}\n\nJSON Output:"

        try:
            response_text = await llm_service.generate(
                prompt=prompt,
                system_prompt=extraction_system_prompt,
                temperature=0.2,
            )

            # Extract JSON block
            clean_json = response_text.strip()
            if "```json" in clean_json:
                start = clean_json.find("```json") + 7
                end = clean_json.find("```", start)
                clean_json = clean_json[start:end].strip()
            elif "```" in clean_json:
                start = clean_json.find("```") + 3
                end = clean_json.find("```", start)
                clean_json = clean_json[start:end].strip()

            parsed = json.loads(clean_json)
            if not isinstance(parsed, list):
                logger.warning("LLM memory extraction returned non-list format: %s", response_text)
                return []

            created_memories: List[Memory] = []
            for item in parsed:
                if isinstance(item, dict) and "content" in item and item["content"].strip():
                    mem_type = item.get("memory_type", "fact")
                    content = item["content"].strip()
                    stored = await self.store_memory(
                        user_id=user_id,
                        memory_type=mem_type,
                        content=content,
                        metadata_={"extracted_automatically": True},
                    )
                    created_memories.append(stored)

            logger.info("Extracted and saved %d memories for user %s", len(created_memories), user_id)
            return created_memories

        except Exception as err:
            logger.error("Failed to extract memories via LLM: %s", err, exc_info=True)
            return []
