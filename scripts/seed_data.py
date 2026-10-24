#!/usr/bin/env python3
"""
==============================================================================
Cognexa AI - Database Seeding Script
==============================================================================
Populates the PostgreSQL database with initial test data:
  1. Default Admin User (admin@cognexa.ai / admin123)
  2. Sample Memories across all 4 types (Episodic, Semantic, Procedural, Working)
  3. Sample Conversation with Message History
  4. Sample Autonomous Task with Multi-Step Execution Plan

Usage:
  python scripts/seed_data.py [--reset]
"""

import argparse
import asyncio
import json
import math
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import List

# ------------------------------------------------------------------------------
# Fallback Password Hashing
# ------------------------------------------------------------------------------
def get_admin_password_hash(password: str = "admin123") -> str:
    """Hash password using bcrypt or passlib if installed, or fallback to valid bcrypt hash."""
    try:
        import bcrypt
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    except ImportError:
        pass

    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.hash(password)
    except ImportError:
        pass

    # Pre-computed bcrypt hash of "admin123" with 12 rounds
    return "$2b$12$6K6Wk56417i8oI4mQd6BtuY76cE6wA9C8/Mh16EwM2Q3fD4V4i78C"


def generate_embedding(seed_val: int, dimensions: int = 384) -> List[float]:
    """
    Generate a normalized deterministic pseudo-embedding vector of unit length.
    Compatible with pgvector cosine distance queries.
    """
    rng = random.Random(seed_val)
    raw_vec = [rng.gauss(0, 1) for _ in range(dimensions)]
    magnitude = math.sqrt(sum(x * x for x in raw_vec))
    if magnitude == 0:
        return [0.0] * dimensions
    return [round(x / magnitude, 6) for x in raw_vec]


def load_env_variables():
    """Load configuration variables from .env if present."""
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]
    for env_path in env_paths:
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
            break


def get_connection_url() -> str:
    """Extract standard asyncpg connection parameters or URL."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Convert SQLAlchemy scheme if present
        if db_url.startswith("postgresql+asyncpg://"):
            return db_url.replace("postgresql+asyncpg://", "postgresql://")
        return db_url

    user = os.getenv("POSTGRES_USER", "cognexa")
    password = os.getenv("POSTGRES_PASSWORD", "cognexa123")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "cognexa_db")
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


# ------------------------------------------------------------------------------
# Database Seeding Logic
# ------------------------------------------------------------------------------
async def seed_database(reset: bool = False):
    """Seed sample data asynchronously into PostgreSQL."""
    try:
        import asyncpg
    except ImportError:
        print("[!] ERROR: 'asyncpg' package is required to run the seed script.")
        print("    Install it via: pip install asyncpg")
        sys.exit(1)

    dsn = get_connection_url()
    print(f"[*] Connecting to database at {dsn.split('@')[-1]}...")

    conn = None
    try:
        conn = await asyncpg.connect(dsn)
    except Exception as exc:
        print(f"[!] Could not connect to PostgreSQL: {exc}")
        print("    Ensure Postgres is running and DATABASE_URL is properly configured.")
        return False

    try:
        async with conn.transaction():
            if reset:
                print("[*] Reset requested. Truncating existing tables...")
                await conn.execute("""
                    TRUNCATE TABLE task_steps, tasks, memories, messages, conversations, users 
                    CASCADE;
                """)

            now = datetime.now(timezone.utc)

            # ------------------------------------------------------------------
            # 1. Admin User
            # ------------------------------------------------------------------
            user_email = "admin@cognexa.ai"
            user_row = await conn.fetchrow("SELECT id FROM users WHERE email = $1", user_email)

            if user_row:
                user_id = user_row["id"]
                print(f"[+] Admin user exists: {user_email} (ID: {user_id})")
            else:
                user_id = uuid.uuid4()
                hashed_pw = get_admin_password_hash("admin123")
                await conn.execute(
                    """
                    INSERT INTO users (id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    user_id,
                    user_email,
                    hashed_pw,
                    "Cognexa System Administrator",
                    True,
                    True,
                    now,
                    now,
                )
                print(f"[+] Created admin user: {user_email} / admin123 (ID: {user_id})")

            # ------------------------------------------------------------------
            # 2. Sample Memories (All 4 Types)
            # ------------------------------------------------------------------
            sample_memories = [
                {
                    "type": "episodic",
                    "content": "User asked to analyze quarterly revenue reports and preferred charts generated with Plotly on 2026-10-10.",
                    "summary": "Quarterly revenue report analysis with Plotly preference",
                    "importance": 0.85,
                    "metadata": {"source": "conversation", "topic": "finance", "visual_format": "plotly"},
                    "seed": 101,
                },
                {
                    "type": "semantic",
                    "content": "User prefers Python for data engineering and FastAPI for microservices with strict Pydantic v2 type annotations.",
                    "summary": "User coding preferences: Python, FastAPI, Pydantic v2",
                    "importance": 0.95,
                    "metadata": {"language": "python", "framework": "fastapi", "typing": "pydantic"},
                    "seed": 102,
                },
                {
                    "type": "procedural",
                    "content": "Standard workflow for deploying services: lint code with ruff, execute pytest test suite, build docker container, deploy to staging environment.",
                    "summary": "Service deployment pipeline procedure",
                    "importance": 0.90,
                    "metadata": {"pipeline": "ci_cd", "steps": ["ruff", "pytest", "docker", "deploy"]},
                    "seed": 103,
                },
                {
                    "type": "working",
                    "content": "Current active task: Building and testing containerized DevOps infrastructure and LangGraph agent workflow for Cognexa AI.",
                    "summary": "Active session infrastructure build",
                    "importance": 0.75,
                    "metadata": {"session_state": "in_progress", "scope": "devops"},
                    "seed": 104,
                },
            ]

            print("[*] Seeding sample memories...")
            for mem in sample_memories:
                vec_str = str(generate_embedding(mem["seed"], 384))
                await conn.execute(
                    """
                    INSERT INTO memories (
                        id, user_id, memory_type, content, summary, embedding, 
                        importance_score, last_accessed_at, access_count, metadata, created_at, updated_at
                    )
                    VALUES ($1, $2, $3::memory_type_enum, $4, $5, $6::vector, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT DO NOTHING;
                    """,
                    uuid.uuid4(),
                    user_id,
                    mem["type"],
                    mem["content"],
                    mem["summary"],
                    vec_str,
                    mem["importance"],
                    now,
                    1,
                    json.dumps(mem["metadata"]),
                    now,
                    now,
                )
            print(f"[+] Seeded {len(sample_memories)} persistent memories (Episodic, Semantic, Procedural, Working)")

            # ------------------------------------------------------------------
            # 3. Sample Conversation & Messages
            # ------------------------------------------------------------------
            conv_id = uuid.uuid4()
            conv_title = "Cognexa Autonomous Agent Pipeline"
            await conn.execute(
                """
                INSERT INTO conversations (id, user_id, title, metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                conv_id,
                user_id,
                conv_title,
                json.dumps({"category": "devops", "agent_mode": "autonomous"}),
                now,
                now,
            )

            messages = [
                {
                    "role": "user",
                    "content": "Hi Cognexa! Can you verify my microservice configuration and plan an automated build script?",
                    "token_count": 19,
                },
                {
                    "role": "assistant",
                    "content": "Hello! I remember your preference for Python, FastAPI, and containerized workflows. I can decompose this into an execution plan, run verification in the Docker sandbox, and commit the verified artifacts. Shall I proceed with the plan?",
                    "token_count": 42,
                },
                {
                    "role": "user",
                    "content": "Yes, go ahead with the autonomous plan.",
                    "token_count": 8,
                },
                {
                    "role": "assistant",
                    "content": "Plan generated: 4 steps identified. Initiating environment validation and test assertions in the sandbox now.",
                    "token_count": 21,
                },
            ]

            print("[*] Seeding sample conversation and messages...")
            for msg in messages:
                await conn.execute(
                    """
                    INSERT INTO messages (
                        id, conversation_id, role, content, token_count, metadata, created_at
                    )
                    VALUES ($1, $2, $3::message_role_enum, $4, $5, $6, $7)
                    """,
                    uuid.uuid4(),
                    conv_id,
                    msg["role"],
                    msg["content"],
                    msg["token_count"],
                    json.dumps({"source": "seed"}),
                    now,
                )
            print(f"[+] Seeded conversation '{conv_title}' with {len(messages)} messages")

            # ------------------------------------------------------------------
            # 4. Sample Autonomous Task & Steps
            # ------------------------------------------------------------------
            task_id = uuid.uuid4()
            task_title = "Deploy Microservice Pipeline with Self-Verification"
            task_description = (
                "Autonomous goal decomposition: Validate environment, run migrations, "
                "execute unit tests in Docker sandbox, and deploy application containers."
            )

            await conn.execute(
                """
                INSERT INTO tasks (
                    id, user_id, conversation_id, title, description, status, result, 
                    error_message, metadata, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, 'in_progress'::task_status_enum, $6, $7, $8, $9, $10)
                """,
                task_id,
                user_id,
                conv_id,
                task_title,
                task_description,
                json.dumps({"progress_percentage": 50}),
                None,
                json.dumps({"priority": "high", "max_retries": 3}),
                now,
                now,
            )

            steps = [
                {
                    "step_number": 1,
                    "title": "Validate Environment Variables and Secret Integrity",
                    "description": "Ensure DATABASE_URL, SECRET_KEY, and OLLAMA_BASE_URL are populated.",
                    "code": "import os\nassert os.getenv('DATABASE_URL') is not None\nprint('Environment OK')",
                    "status": "completed",
                    "output": "Environment validated successfully. All required keys present.",
                    "error": None,
                    "retry_count": 0,
                    "execution_time_ms": 142,
                },
                {
                    "step_number": 2,
                    "title": "Execute Database Vector Schema Verification",
                    "description": "Confirm pgvector extension and memories table indexing.",
                    "code": "SELECT count(*) FROM pg_extension WHERE extname = 'vector';",
                    "status": "completed",
                    "output": "Extension 'vector' confirmed. Schema initialized.",
                    "error": None,
                    "retry_count": 0,
                    "execution_time_ms": 215,
                },
                {
                    "step_number": 3,
                    "title": "Run Sandbox Test Suite and Self-Verification Reflexion",
                    "description": "Run unit assertions in sandbox. If test fails, apply iterative patch.",
                    "code": "pytest tests/ -v",
                    "status": "running",
                    "output": "Running test suite in Docker sandbox...\nPassed: 14, Failed: 0",
                    "error": None,
                    "retry_count": 0,
                    "execution_time_ms": None,
                },
                {
                    "step_number": 4,
                    "title": "Build and Deploy Application Containers",
                    "description": "Build production Docker images and verify healthcheck endpoints.",
                    "code": "docker compose up -d --build",
                    "status": "pending",
                    "output": None,
                    "error": None,
                    "retry_count": 0,
                    "execution_time_ms": None,
                },
            ]

            print("[*] Seeding sample task steps...")
            for step in steps:
                await conn.execute(
                    """
                    INSERT INTO task_steps (
                        id, task_id, step_number, title, description, code, status, 
                        output, error, retry_count, max_retries, execution_time_ms, metadata, created_at, updated_at
                    )
                    VALUES (
                        $1, $2, $3, $4, $5::text, $6::text, $7::step_status_enum, 
                        $8, $9, $10, $11, $12, $13, $14, $15
                    )
                    """,
                    uuid.uuid4(),
                    task_id,
                    step["step_number"],
                    step["title"],
                    step["description"],
                    step["code"],
                    step["status"],
                    step["output"],
                    step["error"],
                    step["retry_count"],
                    3,
                    step["execution_time_ms"],
                    json.dumps({"stage": "pipeline"}),
                    now,
                    now,
                )
            print(f"[+] Seeded task '{task_title}' with {len(steps)} steps")

        print("==============================================================================")
        print("🎉 Database seeding completed successfully!")
        print("   Test credentials: admin@cognexa.ai / admin123")
        print("==============================================================================")
        return True

    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Seed Cognexa AI PostgreSQL Database.")
    parser.add_argument("--reset", action="store_true", help="Truncate existing data before seeding.")
    args = parser.parse_args()

    load_env_variables()
    asyncio.run(seed_database(reset=args.reset))


if __name__ == "__main__":
    main()
