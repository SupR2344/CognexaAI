---
title: Cognexa AI Backend
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🧠 Cognexa AI — FastAPI Asynchronous Microservice

Backend microservice for **Cognexa AI**, featuring:
- Autonomous Agent Planning & Verification
- Hybrid Vector RAG with `all-MiniLM-L6-v2`
- Native Generative Studios (PDF, PPTX, Codebase ZIP)
- Real-Time SSE Token Streaming
- Groq / OpenAI / Ollama Multi-Provider Inference

## Environment Secrets on Hugging Face Spaces

Go to **Settings** -> **Variables and secrets** and add:
- `GROQ_API_KEY`: *(Recommended for ultra-fast free cloud inference)*
- `DATABASE_URL`: `sqlite+aiosqlite:///./cognexa.db` *(or PostgreSQL URL)*
- `SECRET_KEY`: Random 32+ character JWT secret string
