import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from typing import Any, cast

from src.app.webhooks.routers import router as webhooks_router
from src.settings.database import get_db


class FakeRedis:
    def __init__(self):
        self.calls = []

    async def setex(self, key, ttl, value):
        self.calls.append((key, ttl, value))


class StubDB:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


class StubFile:
    def __init__(self):
        self.file_name = None
        self.s3_url = None
        self.s3_key = None


class StubServiceFound:
    last_instance = None

    def __init__(self, db):
        self.db = db
        self.file = StubFile()
        StubServiceFound.last_instance = self

    async def find_file_by_uuid(self, s3_key: str):
        return self.file


class StubServiceNotFound:
    def __init__(self, db):
        self.db = db

    async def find_file_by_uuid(self, s3_key: str):
        return None


@pytest_asyncio.fixture
async def app_base():
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/webhooks")
    return app


@pytest.mark.asyncio
async def test_converter_webhook_success(app_base, monkeypatch):
    fake_redis = FakeRedis()
    stub_db = StubDB()

    # Override DB dependency and patch service + redis in the router module
    async def _override_get_db():
        return stub_db

    overrides = cast(Any, app_base).dependency_overrides
    overrides[get_db] = _override_get_db
    monkeypatch.setattr("src.app.webhooks.routers.FileManagementService", StubServiceFound)
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "file_url": "https://example.com/converted.pdf",
        "new_s3_key": "uuid_file.pdf",
        "status": "success",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/converter-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() == {"message": "File updated successfully"}

    # Validate file updates on the service instance used by the route
    instance = StubServiceFound.last_instance
    assert instance is not None
    file_obj = instance.file
    assert file_obj.file_name == payload["new_s3_key"].split("_")[1]
    assert file_obj.s3_url == payload["file_url"]
    assert file_obj.s3_key == payload["new_s3_key"]

    assert stub_db.committed is True

    # Validate cache write
    assert len(fake_redis.calls) == 1
    key, ttl, value = fake_redis.calls[0]
    assert key == f"file_conversion:{payload['new_s3_key'].split('_')[0]}"
    assert ttl == 60
    cached = json.loads(value)
    assert cached["s3_key"] == payload["new_s3_key"]
    assert cached["new_s3_key"] == payload["new_s3_key"]
    assert cached["file_url"] == payload["file_url"]


@pytest.mark.asyncio
async def test_converter_webhook_file_not_found(app_base, monkeypatch):
    fake_redis = FakeRedis()
    stub_db = StubDB()

    async def _override_get_db():
        return stub_db

    overrides = cast(Any, app_base).dependency_overrides
    overrides[get_db] = _override_get_db
    monkeypatch.setattr("src.app.webhooks.routers.FileManagementService", StubServiceNotFound)
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "file_url": "https://example.com/converted.pdf",
        "new_s3_key": "uuid_file.pdf",
        "status": "success",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/converter-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() == {"error": "File not found"}
    assert stub_db.committed is False
    assert len(fake_redis.calls) == 0


@pytest.mark.asyncio
async def test_converter_webhook_non_success_status_returns_null(app_base, monkeypatch):
    fake_redis = FakeRedis()
    stub_db = StubDB()

    async def _override_get_db():
        return stub_db

    overrides = cast(Any, app_base).dependency_overrides
    overrides[get_db] = _override_get_db
    # Service shouldn't be used in this path, but patch to be safe
    monkeypatch.setattr("src.app.webhooks.routers.FileManagementService", StubServiceFound)
    monkeypatch.setattr("src.app.webhooks.routers.redis", fake_redis)

    payload = {
        "file_url": "https://example.com/converted.pdf",
        "new_s3_key": "uuid_file.pdf",
        "status": "error",
    }

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.post("/webhooks/converter-webhook", content=json.dumps(payload))

    assert resp.status_code == 200
    assert resp.json() is None
    assert stub_db.committed is False
    assert len(fake_redis.calls) == 0

