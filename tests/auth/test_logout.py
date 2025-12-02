import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from src.app.auth.routers import router


@pytest_asyncio.fixture
async def client_with_session():
    """Async test client with SessionMiddleware and a helper route to set session"""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
    app.include_router(router, prefix="/auth")

    @app.post("/test/set-session")
    async def set_session(request: Request):
        body = await request.json()
        # Safely set provided keys into session for testing
        for key in ("user_id", "session_id"):
            if key in body:
                request.session[key] = body[key]
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestLogoutEndpoint:
    """Test suite for the /logout endpoint"""

    @patch("src.app.auth.routers.redis")
    async def test_successful_logout(self, mock_redis, client_with_session: AsyncClient):
        """Logout succeeds when session_id and user_id exist"""
        mock_redis.delete = AsyncMock(return_value=1)

        # Set session via helper route
        await client_with_session.post("/test/set-session", json={"user_id": 123, "session_id": "abc-session"})

        response = await client_with_session.post("/auth/logout")

        assert response.status_code == 200
        assert response.json() == {"message": "Logout successful"}
        mock_redis.delete.assert_awaited_once_with("user:123:session:abc-session")

    @patch("src.app.auth.routers.redis")
    async def test_logout_without_session(self, mock_redis, client_with_session: AsyncClient):
        """Logout fails with 401 when session is missing"""
        mock_redis.delete = AsyncMock()

        response = await client_with_session.post("/auth/logout")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        mock_redis.delete.assert_not_awaited()

    @patch("src.app.auth.routers.redis")
    async def test_logout_missing_user_id(self, mock_redis, client_with_session: AsyncClient):
        """Logout fails when user_id is missing"""
        mock_redis.delete = AsyncMock()

        # Set only session_id
        await client_with_session.post("/test/set-session", json={"session_id": "abc-session"})

        response = await client_with_session.post("/auth/logout")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        mock_redis.delete.assert_not_awaited()

    @patch("src.app.auth.routers.redis")
    async def test_logout_missing_session_id(self, mock_redis, client_with_session: AsyncClient):
        """Logout fails when session_id is missing"""
        mock_redis.delete = AsyncMock()

        # Set only user_id
        await client_with_session.post("/test/set-session", json={"user_id": 123})

        response = await client_with_session.post("/auth/logout")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        mock_redis.delete.assert_not_awaited()
