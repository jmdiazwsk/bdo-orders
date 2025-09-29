# tests/unit/test_health.py
import pytest
from unittest.mock import AsyncMock, Mock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_session as dep_get_session

@pytest.mark.asyncio
async def test_health():
    # 1) Mock de la sesión para evitar conexión a DB
    mock_session = AsyncMock()
    mock_session.execute.return_value = Mock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[dep_get_session] = override_get_session

    # 2) Usar ASGITransport en lugar de app=
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    # 3) Limpiar overrides
    app.dependency_overrides.clear()
