"""Chat and Agent Interaction Routes.

Endpoints for interactive message exchange, real-time SSE token streaming,
and conversation lifecycle management.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.auth.security import get_current_user
from app.agent.graph import generate_approved_task_plan
from app.database import get_db
from app.models.conversation import Conversation, Message
from app.models.memory import Memory
from app.models.task import StepStatus, Task, TaskStep, TaskStatus
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)
from app.services.agent import agent_service
from app.services.embedding import cosine_similarity, get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


async def _get_relevant_memories(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_text: str,
    top_k: int = 4,
) -> List[Dict[str, Any]]:
    """Retrieve top contextual memories for the user based on similarity."""
    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id, Memory.is_active == True)  # noqa: E712
        .order_by(desc(Memory.created_at))
        .limit(25)
    )
    result = await db.execute(stmt)
    memories = result.scalars().all()

    if not memories:
        return []

    query_vec = await run_in_threadpool(get_embedding, query_text)
    scored_memories = []

    for mem in memories:
        if mem.embedding is not None and isinstance(mem.embedding, list) and len(mem.embedding) > 0:
            score = cosine_similarity(query_vec, mem.embedding)
            if score >= 0.62:
                scored_memories.append({
                    "id": str(mem.id),
                    "memory_type": mem.memory_type.value if hasattr(mem.memory_type, "value") else str(mem.memory_type),
                    "content": mem.content,
                    "similarity": round(score, 4),
                })

    scored_memories.sort(key=lambda m: m["similarity"], reverse=True)
    return scored_memories[:top_k]


@router.post(
    "/",
    response_model=ChatResponse,
    summary="Send chat message and receive AI agent response",
)
@router.post(
    "/messages",
    response_model=ChatResponse,
    summary="Send chat message and receive AI agent response (alias)",
)
async def chat_message(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message, recall memories, plan tasks if needed, and produce agent answer."""
    # 1. Fetch or initialize conversation
    conversation = None
    if payload.conversation_id:
        try:
            conv_uuid = uuid.UUID(str(payload.conversation_id))
            stmt = select(Conversation).where(
                Conversation.id == conv_uuid,
                Conversation.user_id == current_user.id,
                Conversation.is_active == True,  # noqa: E712
            )
            res = await db.execute(stmt)
            conversation = res.scalar_one_or_none()
        except (ValueError, TypeError):
            conversation = None

    if not conversation:
        title = payload.message.strip()[:60]
        if len(payload.message.strip()) > 60:
            title += "..."
        conversation = Conversation(
            user_id=current_user.id,
            title=title,
        )
        db.add(conversation)
        await db.flush()

    # 2. Persist incoming user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.flush()

    # 3. Retrieve relevant conversation history
    history_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(10)
    )
    history_res = await db.execute(history_stmt)
    history_messages = list(reversed(history_res.scalars().all()))
    history_payload = [
        {"role": m.role, "content": m.content}
        for m in history_messages
        if m.id != user_msg.id
    ]

    # 4. Contextual memory recall
    relevant_memories = (
        await _get_relevant_memories(db, current_user.id, payload.message)
        if payload.use_memory
        else []
    )

    # 4b. Document RAG Retrieval if attached file is present
    try:
        from app.services.document_rag import document_rag
        parts = re.split(r"User Question(?:/Instruction)?:\s*", payload.message, flags=re.IGNORECASE)
        q_text = parts[-1].strip() if len(parts) > 1 else payload.message
        rag_context = document_rag.build_rag_context(q_text, top_k=4)
        if rag_context:
            relevant_memories.append({
                "memory_type": "document_rag_citation",
                "content": rag_context,
                "created_at": datetime.utcnow().isoformat(),
            })
    except Exception as rag_err:
        logger.warning("RAG retrieval skipped in chat: %s", rag_err)

    # 5. Check if user requested a generative engineering artifact or active model mode
    from app.services.intent_handler import handle_generative_request
    gen_result = await handle_generative_request(
        payload.message,
        user_id=current_user.id,
        db=db,
        conversation_history=history_payload,
        model=payload.model,
    )

    task_created = False
    task_id = None

    if gen_result and gen_result.get("response_text"):
        ai_reply = gen_result["response_text"]
    else:
        # Check if multi-step autonomous task planning is needed
        if agent_service.detect_task_intent(payload.message):
            plan_steps = await generate_approved_task_plan(
                title=payload.message[:80],
                description=payload.message,
                memories=relevant_memories,
            )
            new_task = Task(
                user_id=current_user.id,
                conversation_id=conversation.id,
                title=payload.message[:80],
                description=payload.message,
                status=TaskStatus.pending,
                plan=plan_steps,
                results={"summary": "Validated plan created and waiting for user approval."},
            )
            db.add(new_task)
            await db.flush()

            for step_data in plan_steps:
                step = TaskStep(
                    task_id=new_task.id,
                    step_number=step_data["step_number"],
                    description=step_data["description"],
                    tool_name=step_data.get("tool_name"),
                    tool_input=step_data.get("tool_input", {}),
                    status=StepStatus.pending,
                )
                db.add(step)

            task_created = True
            task_id = new_task.id

        # 6. Generate AI response
        ai_reply = await agent_service.generate_response(
            user_message=payload.message,
            conversation_history=history_payload,
            memories=relevant_memories,
        )

        if task_created:
            ai_reply += (
                f"\n\n**Task Plan Ready:** Task `#{str(task_id)[:8]}` "
                "has a validated workspace plan. Review each step and approve it in the Tasks view "
                "before it runs."
            )


    # 7. Persist AI assistant message
    asst_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_reply,
        metadata_={"task_id": str(task_id) if task_id else None},
    )
    db.add(asst_msg)
    await db.commit()

    return ChatResponse(
        response=ai_reply,
        conversation_id=conversation.id,
        task_created=task_created,
        task_id=task_id,
        memories_used=relevant_memories,
    )


@router.post(
    "/upload",
    summary="Upload document, PDF, code file, or screenshot for AI context extraction",
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Receive an uploaded file, extract text/metadata, and return file analysis handle."""
    from app.services.document_analyzer import analyze_uploaded_file

    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds maximum 30 MB limit.")

    return analyze_uploaded_file(file.filename or "uploaded_file", content)


@router.post(
    "/stream",
    summary="Stream AI agent response via Server-Sent Events (SSE)",
)
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream token chunks over an SSE event-stream while updating conversation logs."""
    # Fetch or create conversation
    conversation = None
    if payload.conversation_id:
        try:
            conv_uuid = uuid.UUID(str(payload.conversation_id))
            stmt = select(Conversation).where(
                Conversation.id == conv_uuid,
                Conversation.user_id == current_user.id,
                Conversation.is_active == True,  # noqa: E712
            )
            res = await db.execute(stmt)
            conversation = res.scalar_one_or_none()
        except (ValueError, TypeError):
            conversation = None

    if not conversation:
        title = payload.message.strip()[:60]
        if len(payload.message.strip()) > 60:
            title += "..."
        conversation = Conversation(user_id=current_user.id, title=title)
        db.add(conversation)
        await db.flush()

    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.commit()

    # Retrieve context
    history_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(desc(Message.created_at))
        .limit(10)
    )
    history_res = await db.execute(history_stmt)
    history_messages = list(reversed(history_res.scalars().all()))
    history_payload = [
        {"role": m.role, "content": m.content}
        for m in history_messages
        if m.id != user_msg.id
    ]

    relevant_memories = (
        await _get_relevant_memories(db, current_user.id, payload.message)
        if payload.use_memory
        else []
    )

    # Document RAG Retrieval if attached file is present
    try:
        from app.services.document_rag import document_rag
        parts = re.split(r"User Question(?:/Instruction)?:\s*", payload.message, flags=re.IGNORECASE)
        q_text = parts[-1].strip() if len(parts) > 1 else payload.message
        rag_context = document_rag.build_rag_context(q_text, top_k=4)
        if rag_context:
            relevant_memories.append({
                "memory_type": "document_rag_citation",
                "content": rag_context,
                "created_at": datetime.utcnow().isoformat(),
            })
    except Exception as rag_err:
        logger.warning("RAG retrieval skipped in stream: %s", rag_err)

    conv_id = conversation.id

    async def event_generator() -> AsyncGenerator[str, None]:
        full_response = []
        task_id = None
        try:
            # Check if user requested a generative engineering artifact or active model mode
            import asyncio
            from app.services.intent_handler import handle_generative_request
            gen_result = await handle_generative_request(
                payload.message,
                user_id=current_user.id,
                db=db,
                conversation_history=history_payload,
                model=payload.model,
            )

            if gen_result and gen_result.get("response_text"):
                response_text = gen_result["response_text"]
                words = response_text.split(" ")
                for i in range(0, len(words), 3):
                    chunk = " ".join(words[i : i + 3]) + (" " if i + 3 < len(words) else "")
                    full_response.append(chunk)
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    await asyncio.sleep(0.035)
            else:
                # Stream tokens immediately as generated
                async for token in agent_service.stream_response(
                    user_message=payload.message,
                    conversation_history=history_payload,
                    memories=relevant_memories,
                ):
                    full_response.append(token)
                    yield f"data: {json.dumps({'chunk': token})}\n\n"


            # Check if an autonomous task plan should be created
            if agent_service.detect_task_intent(payload.message):
                try:
                    plan_steps = await generate_approved_task_plan(
                        title=payload.message[:80],
                        description=payload.message,
                        memories=relevant_memories,
                    )
                    from app.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as session:
                        new_task = Task(
                            user_id=current_user.id,
                            conversation_id=conv_id,
                            title=payload.message[:80],
                            description=payload.message,
                            status=TaskStatus.pending,
                            plan=plan_steps,
                            results={"summary": "Validated plan created and waiting for user approval."},
                        )
                        session.add(new_task)
                        await session.flush()
                        for step_data in plan_steps:
                            session.add(TaskStep(
                                task_id=new_task.id,
                                step_number=step_data["step_number"],
                                description=step_data["description"],
                                tool_name=step_data.get("tool_name"),
                                tool_input=step_data.get("tool_input", {}),
                                status=StepStatus.pending,
                            ))
                        await session.commit()
                        task_id = new_task.id
                except Exception as task_err:
                    logger.warning("Background task formulation error: %s", task_err)

            if task_id:
                task_note = (
                    f"\n\n**Task Plan Ready:** Task `#{str(task_id)[:8]}` "
                    "has a validated workspace plan. Review each step and approve it in the Tasks view "
                    "before it runs."
                )
                full_response.append(task_note)
                yield f"data: {json.dumps({'chunk': task_note})}\n\n"

            # Finalize and record message
            complete_text = "".join(full_response)
            yield f"data: {json.dumps({'done': True, 'conversation_id': str(conv_id), 'task_created': bool(task_id), 'task_id': str(task_id) if task_id else None, 'memories_used': relevant_memories})}\n\n"

            # Store assistant message in background
            try:
                from app.database import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    db_asst = Message(
                        conversation_id=conv_id,
                        role="assistant",
                        content=complete_text,
                        metadata_={"task_id": str(task_id) if task_id else None},
                    )
                    session.add(db_asst)
                    await session.commit()
            except Exception as save_err:
                logger.error("Failed saving streamed assistant message: %s", save_err)

        except Exception as stream_err:
            logger.error("Error in SSE generator: %s", stream_err)
            yield f"data: {json.dumps({'error': str(stream_err)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.get(
    "/conversations",
    response_model=List[ConversationListResponse],
    summary="List all user conversations",
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ConversationListResponse]:
    """Retrieve all active conversations belonging to the authenticated user."""
    stmt = (
        select(
            Conversation,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,  # noqa: E712
        )
        .group_by(Conversation.id)
        .order_by(desc(Conversation.updated_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for conv, count in rows:
        items.append(
            ConversationListResponse(
                id=conv.id,
                title=conv.title,
                is_active=conv.is_active,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=count,
            )
        )
    return items


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details and full message transcript",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Fetch a single conversation with all its associated turns."""
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,  # noqa: E712
        )
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationResponse.model_validate(conversation)


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation thread",
)
async def create_conversation(
    payload: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Explicitly create a new conversation for the user."""
    title = "New Conversation"
    if payload and "title" in payload and payload["title"]:
        title = str(payload["title"]).strip()[:80]
    conv = Conversation(user_id=current_user.id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        is_active=conv.is_active,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[],
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
    summary="Get transcript of messages for a conversation",
)
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[MessageResponse]:
    """Fetch all messages for a specific conversation."""
    stmt = (
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,
        )
        .order_by(Message.created_at.asc())
    )
    res = await db.execute(stmt)
    messages = res.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.delete(
    "/conversations/{conversation_id}",
    summary="Soft-delete a conversation thread",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Mark a conversation as deleted."""
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
        Conversation.is_active == True,  # noqa: E712
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    conv.is_active = False
    await db.commit()

    return {"status": "deleted", "conversation_id": str(conversation_id)}
