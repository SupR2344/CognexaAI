"""Application Configuration.

Loads environment variables using Pydantic Settings.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and configuration parameters."""

    # Project metadata
    PROJECT_NAME: str = "Cognexa AI"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://cognexa:cognexa123@localhost:5432/cognexa_db",
        description="Async PostgreSQL connection string with asyncpg driver",
    )

    # LLM / Ollama & OpenAI / Groq Configuration
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL for the Ollama inference server",
    )
    OLLAMA_MODEL: str = Field(
        default="qwen2.5:7b",
        description="Default Ollama model name for agent reasoning and generation",
    )
    GROQ_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional Groq Cloud API key for ultra-fast (500 tps) inference",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="Optional OpenAI or OpenAI-compatible API key",
    )
    OPENAI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="Default OpenAI model name when OPENAI_API_KEY is configured",
    )
    OPENAI_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible API",
    )

    # Embeddings
    EMBEDDING_MODEL: str = Field(
        default="all-MiniLM-L6-v2",
        description="HuggingFace sentence-transformers model name (384 dimensions)",
    )
    EMBEDDING_DIMENSION: int = 384

    # Security & JWT Auth
    SECRET_KEY: str = Field(
        default="your-secret-key-change-this-in-production-cognexa-ai",
        description="JWT secret key for signing tokens",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT token signature algorithm",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        description="JWT access token expiration time in minutes (1440 = 24h)",
    )

    # Sandbox & Execution Environment
    DOCKER_SANDBOX_IMAGE: str = Field(
        default="cognexa-backend:local",
        description="Prebuilt image used for isolated task execution",
    )
    SANDBOX_TEST_TIMEOUT: int = Field(
        default=180,
        description="Maximum execution time in seconds for sandboxed test runs",
    )
    MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for tool execution and agent steps",
    )
    SANDBOX_TIMEOUT: int = Field(
        default=30,
        description="Execution timeout in seconds for sandboxed actions",
    )

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:8000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached instance of application settings."""
    return Settings()


settings = get_settings()
