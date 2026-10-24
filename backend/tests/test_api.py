"""Unit tests for FastAPI endpoints and system health probing."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Verify that root system information endpoint responds with status 200."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "operational"
        assert "Cognexa AI" in data.get("project", "")


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify that health check endpoint responds with healthy/degraded status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data


@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Verify the system benchmark endpoint provides a structured deployment snapshot."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "system" in data
        assert "benchmark" in data
        assert "status" in data
        assert "scores" in data["benchmark"]
