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
async def test_analysis_webhook_success(app_base, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "s3_key": "uuid777_file.txt",
        "polarity": 0.25,
        "subjectivity": 0.6,
        "objective_sentiment_score": 0.4,
        "polarity_status": "positive",
        "polarity_description": "Mostly positive",
        "subjectivity_status": "subjective",
        "subjectivity_description": "Contains opinions",
        "objective_sentiment_status": "medium",
        "objective_sentiment_description": "Balanced sentiments",
        "status": "success",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/analysis-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() == {"message": "Tonality analysis result cached"}

    # Cache write validated
    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == "tonality_analysis:uuid777"
    assert ttl == 60
    cached = json.loads(value)
    for k, v in payload.items():
        assert cached[k] == v


@pytest.mark.asyncio
async def test_analysis_webhook_non_success_returns_null(app_base, monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "s3_key": "uuid001_file.txt",
        "polarity": -0.1,
        "subjectivity": 0.2,
        "objective_sentiment_score": 0.8,
        "polarity_status": "negative",
        "polarity_description": "Slightly negative",
        "subjectivity_status": "objective",
        "subjectivity_description": "Mostly facts",
        "objective_sentiment_status": "high",
        "objective_sentiment_description": "Strong objective tone",
        "status": "error",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/analysis-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() is None

    # Cache still written even on non-success
    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == "tonality_analysis:uuid001"
    assert ttl == 60
    cached = json.loads(value)
    for k, v in payload.items():
        assert cached[k] == v
