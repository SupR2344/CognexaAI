"""Database Configuration and Async Session Management.

Sets up SQLAlchemy async engine, sessionmaker, declarative base,
and database lifecycle routines (supporting both PostgreSQL/pgvector and SQLite).
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# Determine effective database connection string
db_url = settings.DATABASE_URL

if "postgresql" in db_url:
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        try:
            import aiosqlite  # noqa: F401
            logger.warning(
                "Driver 'asyncpg' is not installed in current environment. "
                "Using local SQLite async database (cognexa.db) for native operation."
            )
            db_url = "sqlite+aiosqlite:///./cognexa.db"
        except ImportError:
            raise RuntimeError(
                "\n"
                "==============================================================================\n"
                "🚨 COGNEXA AI: MISSING ASYNC DATABASE DRIVER\n"
                "Neither 'asyncpg' nor 'aiosqlite' is currently installed in your Python environment.\n"
                "\n"
                "To install the backend dependencies, run in your terminal:\n"
                "    python -m pip install -r requirements.txt\n"
                "\n"
                "Or with Conda:\n"
                "    conda install -y -c conda-forge asyncpg aiosqlite\n"
                "==============================================================================\n"
            ) from None

# Engine configuration parameters
engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

if "sqlite" not in db_url:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    })
else:
    engine_kwargs.update({
        "connect_args": {"timeout": 30.0},
    })

# Create SQLAlchemy Async Engine
engine = create_async_engine(db_url, **engine_kwargs)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy database models."""
    __allow_unmapped__ = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency provider for asynchronous database sessions.

    Yields:
        AsyncSession: Active SQLAlchemy async session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database schemas, extensions, and tables.

    Enables the pgvector extension if available on PostgreSQL,
    then generates all registered SQLAlchemy model tables.
    """
    global engine
    logger.info("Initializing database schemas and tables on: %s", engine.url)

    # Import models here to ensure metadata registration
    import app.models  # noqa: F401

    try:
        async with engine.begin() as conn:
            if "sqlite" in str(engine.url):
                try:
                    await conn.execute(text("PRAGMA journal_mode=WAL;"))
                    await conn.execute(text("PRAGMA busy_timeout=30000;"))
                except Exception as pragma_err:
                    logger.warning("Could not set SQLite pragmas: %s", pragma_err)

            if "postgresql" in str(engine.url):
                try:
                    logger.info("Ensuring 'vector' extension is enabled in PostgreSQL...")
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    logger.info("pgvector extension check passed.")
                except Exception as exc:
                    logger.warning(
                        "Notice: Could not enable 'vector' extension directly: %s. "
                        "Continuing with schema setup.",
                        exc,
                    )

            logger.info("Creating all database tables via SQLAlchemy metadata...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables initialized successfully.")
    except Exception as conn_err:
        if "postgresql" in str(engine.url):
            logger.warning(
                "PostgreSQL connection to %s failed (%s). "
                "Switching automatically to local SQLite async database (cognexa.db)...",
                engine.url,
                conn_err,
            )
            engine = create_async_engine(
                "sqlite+aiosqlite:///./cognexa.db",
                echo=settings.DEBUG,
                future=True,
            )
            AsyncSessionLocal.configure(bind=engine)
            async with engine.begin() as sqlite_conn:
                await sqlite_conn.run_sync(Base.metadata.create_all)
            logger.info("Local SQLite database initialized successfully (cognexa.db).")
        else:
            raise conn_err

    # Auto-seed default admin user if not present or heal password
    try:
        async with AsyncSessionLocal() as session:
            from app.models.user import User
            from app.auth.security import get_password_hash, verify_password
            from sqlalchemy import select, func, or_

            res = await session.execute(
                select(User).where(
                    or_(
                        func.lower(User.email) == "admin@cognexa.ai",
                        func.lower(User.username) == "admin",
                    )
                )
            )
            admin_user = res.scalar_one_or_none()
            if not admin_user:
                logger.info("Auto-seeding default administrator (admin@cognexa.ai)...")
                admin_user = User(
                    username="admin",
                    email="admin@cognexa.ai",
                    hashed_password=get_password_hash("admin123"),
                    is_active=True,
                )
                session.add(admin_user)
                await session.commit()
                logger.info("Default administrator seeded successfully (admin@cognexa.ai / admin123).")
            else:
                needs_update = False
                if not admin_user.is_active:
                    admin_user.is_active = True
                    needs_update = True
                try:
                    if not verify_password("admin123", admin_user.hashed_password):
                        admin_user.hashed_password = get_password_hash("admin123")
                        needs_update = True
                except Exception:
                    admin_user.hashed_password = get_password_hash("admin123")
                    needs_update = True

                if needs_update:
                    await session.commit()
                    logger.info("Default administrator account refreshed and verified successfully.")

            # Auto-seed foundational verified knowledge into user memory if empty
            try:
                from app.models.memory import Memory, MemoryType
                mem_count_res = await session.execute(
                    select(func.count(Memory.id)).where(Memory.user_id == admin_user.id)
                )
                count = mem_count_res.scalar() or 0
                if count == 0:
                    from app.services.embedding import get_embedding
                    seed_knowledge = [
                        (
                            "Cognexa Autonomous System Architecture: Multi-tier microservice combining LangGraph state machines, pgvector/SQLite vector embeddings, and sandboxed execution environments.",
                            {"category": "architecture", "domain": "software_engineering"}
                        ),
                        (
                            "Distributed Systems Core Theorems: CAP Theorem dictates trade-offs between Consistency and Availability during network partitions; PACELC extends this to Latency vs Consistency under normal operation.",
                            {"category": "distributed_systems", "domain": "system_design"}
                        ),
                        (
                            "Modern Transformer & LLM Foundations: Scaled Dot-Product Attention Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V with Rotary Position Embeddings (RoPE) and Direct Preference Optimization (DPO).",
                            {"category": "ai", "domain": "generative_ai"}
                        ),
                        (
                            "1950 Global Epoch & Constitutional Sovereignty: Enactment of the Constitution of India on 26 January 1950 founding the Republic; start of the Korean War; Alan Turing's introduction of the Turing Test.",
                            {"category": "history", "domain": "world_history"}
                        ),
                        (
                            "Full-Stack Web Engineering Standards: Next.js 14 App Router with React Server Components, FastAPI async endpoints with Pydantic contracts, and Server-Sent Events (SSE) streaming.",
                            {"category": "fullstack", "domain": "web_development"}
                        ),
                    ]
                    for content, meta in seed_knowledge:
                        emb = get_embedding(content)
                        session.add(
                            Memory(
                                user_id=admin_user.id,
                                memory_type=MemoryType.verified_knowledge.value,
                                content=content,
                                confidence=0.98,
                                embedding=emb,
                                metadata_=meta,
                                is_active=True,
                            )
                        )
                    await session.commit()
                    logger.info("Foundational verified knowledge memories seeded successfully.")
            except Exception as mem_seed_err:
                logger.warning("Could not auto-seed verified knowledge memories: %s", mem_seed_err)
    except Exception as seed_exc:
        logger.warning("Could not auto-seed or heal default user: %s", seed_exc)
