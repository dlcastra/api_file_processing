import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from src.app.auth.routers import router
from src.app.auth.utils import blacklist_check


@pytest_asyncio.fixture
async def client_with_session_and_override():
    """Async client with SessionMiddleware, helper route to set session, and blacklist override."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    # Override blacklist dependency to a no-op for testing
    app.dependency_overrides = {blacklist_check: lambda: None}

    app.include_router(router, prefix="/auth")

    @app.post("/test/set-session")
    async def set_session(request: Request):
        body = await request.json()
        for key in ("user_id", "session_id"):
            if key in body:
                request.session[key] = body[key]
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestLogoutOthersEndpoint:
    """Tests for the /logout-others endpoint"""

    @patch("src.app.auth.routers.redis")
    @patch("src.app.auth.routers.add_to_blacklist")
    async def test_logout_others_success(
        self, mock_add_to_blacklist, mock_redis, client_with_session_and_override: AsyncClient
    ):
        """Deletes all other sessions, keeps current; returns count and calls blacklist + delete."""
        # Simulate keys in Redis: two other sessions and the current one
        user_id = 123
        current_session = "curr-session"
        other_sessions = ["sess-1", "sess-2"]
        keys = [
            f"user:{user_id}:session:{other_sessions[0]}".encode("utf-8"),
            f"user:{user_id}:session:{other_sessions[1]}".encode("utf-8"),
            f"user:{user_id}:session:{current_session}".encode("utf-8"),
        ]
        mock_redis.keys = AsyncMock(return_value=keys)
        mock_redis.delete = AsyncMock(return_value=2)
        mock_add_to_blacklist.return_value = AsyncMock()

        # Set session via helper route
        await client_with_session_and_override.post(
            "/test/set-session", json={"user_id": user_id, "session_id": current_session}
        )

        response = await client_with_session_and_override.post("/auth/logout-others")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout others successfully"
        assert data["count"] == "2"
        mock_add_to_blacklist.assert_called_once()
        # Ensure blacklist received the two other session IDs
        args, kwargs = mock_add_to_blacklist.call_args
        assert args[0] is mock_redis
        assert sorted(args[1]) == sorted(other_sessions)
        # Ensure delete called with the two other session keys
        mock_redis.delete.assert_awaited_once()
        del_args, del_kwargs = mock_redis.delete.call_args
        assert sorted([k for k in del_args]) == sorted(
            [
                f"user:{user_id}:session:{other_sessions[0]}",
                f"user:{user_id}:session:{other_sessions[1]}",
            ]
        )

    @patch("src.app.auth.routers.redis")
    @patch("src.app.auth.routers.add_to_blacklist")
    async def test_logout_others_no_external_sessions(
        self, mock_add_to_blacklist, mock_redis, client_with_session_and_override: AsyncClient
    ):
        """If only current session exists, returns 'No external sessions' and does not delete or blacklist."""
        user_id = 456
        current_session = "only-session"
        keys = [f"user:{user_id}:session:{current_session}".encode("utf-8")]
        mock_redis.keys = AsyncMock(return_value=keys)
        mock_redis.delete = AsyncMock()
        mock_add_to_blacklist.return_value = AsyncMock()

        await client_with_session_and_override.post(
            "/test/set-session", json={"user_id": user_id, "session_id": current_session}
        )

        response = await client_with_session_and_override.post("/auth/logout-others")

        assert response.status_code == 200
        assert response.json() == {"message": "No external sessions"}
        mock_add_to_blacklist.assert_not_called()
        mock_redis.delete.assert_not_awaited()

    @patch("src.app.auth.routers.redis")
    async def test_logout_others_missing_session_id(self, mock_redis, client_with_session_and_override: AsyncClient):
        """Fails with 401 when session_id is missing."""
        mock_redis.keys = AsyncMock()
        mock_redis.delete = AsyncMock()

        await client_with_session_and_override.post("/test/set-session", json={"user_id": 777})
        response = await client_with_session_and_override.post("/auth/logout-others")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        mock_redis.keys.assert_not_awaited()
        mock_redis.delete.assert_not_awaited()

    @patch("src.app.auth.routers.redis")
    async def test_logout_others_missing_user_id(self, mock_redis, client_with_session_and_override: AsyncClient):
        """Fails with 401 when user_id is missing."""
        mock_redis.keys = AsyncMock()
        mock_redis.delete = AsyncMock()

        await client_with_session_and_override.post("/test/set-session", json={"session_id": "some-session"})
        response = await client_with_session_and_override.post("/auth/logout-others")

        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
        mock_redis.keys.assert_not_awaited()
        mock_redis.delete.assert_not_awaited()
