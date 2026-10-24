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

    # Auto-seed default admin user if not present
    try:
        async with AsyncSessionLocal() as session:
            from app.models.user import User
            from app.auth.security import get_password_hash
            from sqlalchemy import select

            res = await session.execute(select(User).where(User.email == "admin@cognexa.ai"))
            if not res.scalar_one_or_none():
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
    except Exception as seed_exc:
        logger.warning("Could not auto-seed default user: %s", seed_exc)
