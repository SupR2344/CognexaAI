"""Cognitive Memory Management Routes.

Enables manual recording, semantic vector search, editing, and pruning
of long-term agent memories.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_current_user
from app.database import get_db
from app.models.memory import Memory, MemoryType
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryTypeEnum,
    MemoryUpdate,
)
from app.services.embedding import cosine_similarity, get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get(
    "/",
    response_model=List[MemoryResponse],
    summary="List stored memories for authenticated user",
)
async def list_memories(
    memory_type: Optional[MemoryTypeEnum] = Query(
        default=None,
        description="Filter by specific memory classification",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MemoryResponse]:
    """Retrieve user memories with optional category filtering and pagination."""
    stmt = select(Memory).where(
        Memory.user_id == current_user.id,
        Memory.is_active == True,  # noqa: E712
    )

    if memory_type is not None:
        stmt = stmt.where(Memory.memory_type == memory_type.value)

    stmt = stmt.order_by(desc(Memory.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    memories = result.scalars().all()

    return [MemoryResponse.model_validate(m) for m in memories]


@router.post(
    "/",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new cognitive memory entry",
)
async def create_memory(
    payload: MemoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """Store a new long-term memory and generate its dense vector representation."""
    # Compute 384-dimensional dense vector
    vector = get_embedding(payload.content)

    memory = Memory(
        user_id=current_user.id,
        memory_type=payload.memory_type.value,
        content=payload.content.strip(),
        embedding=vector,
        metadata_=payload.metadata_ or {},
        is_active=True,
    )
    db.add(memory)
    await db.commit()
    await db.refresh(memory)

    logger.info("Created memory '%s' (%s) for user %s", memory.id, memory.memory_type, current_user.username)
    return MemoryResponse.model_validate(memory)


@router.post(
    "/search",
    response_model=MemorySearchResponse,
    summary="Perform semantic vector search across user memories",
)
async def search_memories(
    payload: MemorySearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemorySearchResponse:
    """Find top semantically matching memories using cosine distance on dense vectors."""
    query_vector = get_embedding(payload.query)

    stmt = select(Memory).where(
        Memory.user_id == current_user.id,
        Memory.is_active == True,  # noqa: E712
    )

    if payload.memory_type is not None:
        stmt = stmt.where(Memory.memory_type == payload.memory_type.value)

    result = await db.execute(stmt)
    candidates = result.scalars().all()

    scored_items: List[tuple[Memory, float]] = []
    for mem in candidates:
        similarity = 0.0
        if mem.embedding is not None and isinstance(mem.embedding, list):
            similarity = cosine_similarity(query_vector, mem.embedding)
        elif payload.query.lower() in mem.content.lower():
            similarity = 0.7
        scored_items.append((mem, similarity))

    # Sort descending by similarity
    scored_items.sort(key=lambda item: item[1], reverse=True)
    top_items = scored_items[: payload.limit]

    output_memories: List[MemoryResponse] = []
    for mem, score in top_items:
        m_resp = MemoryResponse.model_validate(mem)
        m_resp.similarity = round(score, 4)
        output_memories.append(m_resp)

    return MemorySearchResponse(
        query=payload.query,
        memories=output_memories,
        total=len(output_memories),
    )


@router.put(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="Update an existing cognitive memory",
)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    """Modify content or metadata of a memory and recompute vector if content changed."""
    stmt = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == current_user.id,
        Memory.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    if payload.content is not None and payload.content.strip():
        memory.content = payload.content.strip()
        memory.embedding = get_embedding(payload.content.strip())

    if payload.memory_type is not None:
        memory.memory_type = payload.memory_type.value

    if payload.metadata_ is not None:
        memory.metadata_ = payload.metadata_

    await db.commit()
    await db.refresh(memory)

    return MemoryResponse.model_validate(memory)


@router.delete(
    "/{memory_id}",
    summary="Delete a memory item",
)
async def delete_memory(
    memory_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Deactivate or remove a memory record."""
    stmt = select(Memory).where(
        Memory.id == memory_id,
        Memory.user_id == current_user.id,
        Memory.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    memory = result.scalar_one_or_none()

    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found",
        )

    memory.is_active = False
    await db.commit()

    return {"status": "deleted", "id": str(memory_id)}
