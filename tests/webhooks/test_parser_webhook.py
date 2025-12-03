import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from src.app.webhooks.routers import router as webhooks_router


class FakeRedis:
    def __init__(self):
        self.calls = []

    async def setex(self, key, ttl, value):
        self.calls.append((key, ttl, value))


@pytest_asyncio.fixture
async def app_base():
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/webhooks")
    return app


@pytest.mark.asyncio
async def test_parser_webhook_success(app_base, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "count": 2,
        "sentences": ["Hello world", "How are you?"],
        "s3_key": "uuid123_file.txt",
        "status": "success",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/parser-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() == {"message": "Parsing result cached"}

    # Cache write validated
    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == "file_parsing:uuid123"
    assert ttl == 60
    cached = json.loads(value)
    assert cached["s3_key"] == payload["s3_key"]
    assert cached["count"] == payload["count"]
    assert cached["sentences"] == payload["sentences"]
    assert cached["status"] == payload["status"]


@pytest.mark.asyncio
async def test_parser_webhook_non_success_returns_null(app_base, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "count": 0,
        "sentences": [],
        "s3_key": "uuid999_file.txt",
        "status": "error",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/parser-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() is None

    # Cache still written even on non-success
    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == "file_parsing:uuid999"
    assert ttl == 60
    cached = json.loads(value)
    assert cached["s3_key"] == payload["s3_key"]
    assert cached["status"] == payload["status"]
