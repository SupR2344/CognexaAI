"""Cognexa AI - Autonomous, Self-Improving Agentic Backend Application.

Main FastAPI application setup with CORS middleware, lifespan events,
database table initialization, and API routers.
Version 1.0.2 - Universal Domain Support & Full Token Output
"""

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal, engine, init_db
from app.routes import (
    auth_router,
    chat_router,
    dashboard_router,
    memory_router,
    tasks_router,
)
from app.services.benchmark_service import BenchmarkService
from app.services.task_recovery import recover_interrupted_tasks

# Configure application logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cognexa-ai")
benchmark_service = BenchmarkService()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager to handle startup and shutdown events."""
    logger.info("Starting up Cognexa AI Backend...")
    try:
        await init_db()
        logger.info("Database and vector extensions verified successfully.")
        async with AsyncSessionLocal() as session:
            recovered_tasks = await recover_interrupted_tasks(session)
        if recovered_tasks:
            logger.warning(
                "Recovered %s task(s) interrupted during a previous backend run.",
                recovered_tasks,
            )
    except Exception as exc:
        logger.error("Database startup or task recovery encountered an error: %s", exc)
        # We do not crash the app so that dev environments or docs are still accessible

    yield

    logger.info("Shutting down Cognexa AI Backend and releasing database pools...")
    await engine.dispose()
    logger.info("Backend shut down cleanly.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=(
        "Cognexa AI: Next-generation autonomous, self-improving agentic workflow system "
        "featuring long-term vector memory, tool calling, and human-in-the-loop task orchestration."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API subrouters (supporting both /api and root paths)
for pfx in ["/api", ""]:
    app.include_router(auth_router, prefix=pfx)
    app.include_router(chat_router, prefix=pfx)
    app.include_router(memory_router, prefix=pfx)
    app.include_router(tasks_router, prefix=pfx)
    app.include_router(dashboard_router, prefix=pfx)


@app.get(
    "/",
    tags=["system"],
    summary="Root service information endpoint",
)
async def root() -> Dict[str, Any]:
    """Return high-level metadata and operational status of Cognexa AI."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "operational",
        "documentation": "/docs",
        "ollama_model": settings.OLLAMA_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


@app.get(
    "/downloads/{filename}",
    tags=["exports"],
    summary="Download generated files (PPTX, PDF, ZIP, Images)",
)
@app.get(
    "/api/downloads/{filename}",
    tags=["exports"],
    summary="Download generated files (alias)",
)
async def download_export(filename: str) -> Any:
    """Download packaged zip archive, pptx presentation, pdf report, or image artifact."""
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    exports_dir = Path("exports").resolve()
    file_path = (exports_dir / filename).resolve()

    if not str(file_path).startswith(str(exports_dir)) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested file was not found.")

    media_map = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pdf": "application/pdf",
        ".zip": "application/zip",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }
    ext = file_path.suffix.lower()
    media_type = media_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


@app.get(
    "/uploads/{filename}",
    tags=["uploads"],
    summary="View or download uploaded files",
)
@app.get(
    "/api/uploads/{filename}",
    tags=["uploads"],
    summary="View or download uploaded files (alias)",
)
async def get_uploaded_file(filename: str) -> Any:
    """Serve uploaded documents and images."""
    from pathlib import Path
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    uploads_dir = Path("uploads").resolve()
    file_path = (uploads_dir / filename).resolve()

    if not str(file_path).startswith(str(uploads_dir)) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested upload was not found.")

    media_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".json": "application/json",
    }
    ext = file_path.suffix.lower()
    media_type = media_map.get(ext, "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )



@app.get(
    "/health",
    tags=["system"],
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint for liveness and database probing",
)
@app.get(
    "/api/health",
    tags=["system"],
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint (alias)",
)
async def health_check() -> Dict[str, Any]:
    """Perform health checks on database connectivity and runtime state."""
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
    except Exception as exc:
        logger.warning("Health probe database warning: %s", exc)
        db_status = f"unreachable ({type(exc).__name__})"

    return {
        "status": "healthy" if "unreachable" not in db_status else "degraded",
        "database": db_status,
        "version": settings.PROJECT_VERSION,
        "model": settings.OLLAMA_MODEL,
    }


@app.get(
    "/metrics",
    tags=["system"],
    status_code=status.HTTP_200_OK,
    summary="System-wide benchmark metrics for the running Cognexa deployment",
)
async def system_metrics() -> Dict[str, Any]:
    """Return a compact system benchmark snapshot for the active deployment."""
    async with AsyncSessionLocal() as session:
        return await benchmark_service.build_system_snapshot(session)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
