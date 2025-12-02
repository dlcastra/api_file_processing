import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from src.app.auth.routers import router


@pytest_asyncio.fixture
async def client():
    """Fixture providing an async test client"""
    app = FastAPI()
    app.include_router(router, prefix="/auth")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
