import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from starlette.middleware.sessions import SessionMiddleware

from src.app.file_management.routers import router as files_router, get_file_manager
from src.app.auth.utils import blacklist_check
from src.app.responses.statuses import ResponseErrorMessage, ProcessingStatus


class StubFileManagementServiceDownloadSuccess:
    async def download_file(self, s3_key: str):
        return {"message": "converted", "s3_key": s3_key}


class StubFileManagementServiceDownloadError:
    async def download_file(self, s3_key: str):
        raise Exception("Download failed")


async def _noop_blacklist_check():
    return True


@pytest_asyncio.fixture
async def app_base():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
    app.include_router(files_router, prefix="/files")
    app.dependency_overrides[blacklist_check] = _noop_blacklist_check
    return app


@pytest.mark.asyncio
async def test_convert_success(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceDownloadSuccess()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("ok", True)

    async def _mock_wait_for_cache(s3_key, cache_key):
        return {
            "status": ProcessingStatus.SUCCESS,
            "s3_key": s3_key,
        }

    # Monkeypatch external calls used in the route
    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt", "format_from": "txt", "format_to": "pdf"}
        resp = await ac.post("/files/convert", content=json.dumps(payload))
        # On success, route-level status_code=201 should be used when returning a dict
        assert resp.status_code == 201
        data = resp.json()
        assert data["message"] == "converted"
        assert data["s3_key"] == "uuid_key_file.txt"


@pytest.mark.asyncio
async def test_convert_sqs_error(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceDownloadSuccess()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("enqueue error", False)

    async def _mock_wait_for_cache(s3_key, cache_key):
        return None

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt", "format_from": "txt", "format_to": "pdf"}
        resp = await ac.post("/files/convert", content=json.dumps(payload))
        assert resp.status_code == 500
        data = resp.json()
        # Route returns JSONResponse with message from SQS
        assert data["message"] == "enqueue error"


@pytest.mark.asyncio
async def test_convert_timeout(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceDownloadSuccess()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("ok", True)

    async def _mock_wait_for_cache(s3_key, cache_key):
        # Simulate no cached data -> timeout
        return None

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt", "format_from": "txt", "format_to": "pdf"}
        resp = await ac.post("/files/convert", content=json.dumps(payload))
        assert resp.status_code == 504
        data = resp.json()
        assert data["message"] == ResponseErrorMessage.TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_convert_internal_error(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceDownloadSuccess()

    async def _mock_send_message_to_sqs(queue_url, body):
        # Simulate unexpected exception in SQS send
        raise Exception("boom")

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt", "format_from": "txt", "format_to": "pdf"}
        resp = await ac.post("/files/convert", content=json.dumps(payload))
        assert resp.status_code == 500
        data = resp.json()
        assert data["detail"] == ResponseErrorMessage.INTERNAL_ERROR
