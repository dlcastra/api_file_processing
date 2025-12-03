import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from starlette.middleware.sessions import SessionMiddleware

from src.app.file_management.routers import router as files_router, get_file_manager
from src.app.auth.utils import blacklist_check
from src.app.responses.statuses import ResponseErrorMessage, ProcessingStatus


class StubFileManagementServiceUserFileYes:
    async def check_user_file(self, s3_key: str, user_id: int) -> bool:
        return True


class StubFileManagementServiceUserFileNo:
    async def check_user_file(self, s3_key: str, user_id: int) -> bool:
        return False


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
async def test_tonality_analysis_success(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceUserFileYes()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("ok", True)

    async def _mock_wait_for_cache(s3_key, cache_key):
        return {
            "status": ProcessingStatus.SUCCESS,
            "s3_key": s3_key,
            "polarity": 0.4,
            "subjectivity": 0.6,
            "objective_sentiment_score": 0.2,
            "polarity_status": "neutral",
            "polarity_description": "Neutral polarity",
            "subjectivity_status": "subjective",
            "subjectivity_description": "Rather subjective",
            "objective_sentiment_status": "low",
            "objective_sentiment_description": "Low objective sentiment",
        }

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt"}
        resp = await ac.post("/files/tonality-analysis", content=json.dumps(payload))
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == ProcessingStatus.SUCCESS
        assert data["s3_key"] == "uuid_key_file.txt"
        assert data["polarity"] == 0.4
        assert data["subjectivity"] == 0.6
        assert data["objective_sentiment_score"] == 0.2


@pytest.mark.asyncio
async def test_tonality_analysis_not_user_file(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceUserFileNo()

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt"}
        resp = await ac.post("/files/tonality-analysis", content=json.dumps(payload))
        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == ResponseErrorMessage.FILE_DOES_NOT_EXIST


@pytest.mark.asyncio
async def test_tonality_analysis_sqs_error(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceUserFileYes()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("enqueue error", False)

    async def _mock_wait_for_cache(s3_key, cache_key):
        return None

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt"}
        resp = await ac.post("/files/tonality-analysis", content=json.dumps(payload))
        assert resp.status_code == 500
        data = resp.json()
        assert data["message"] == "enqueue error"


@pytest.mark.asyncio
async def test_tonality_analysis_timeout(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceUserFileYes()

    async def _mock_send_message_to_sqs(queue_url, body):
        return ("ok", True)

    async def _mock_wait_for_cache(s3_key, cache_key):
        return None

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)
    monkeypatch.setattr("src.app.file_management.routers.wait_for_cache", _mock_wait_for_cache)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt"}
        resp = await ac.post("/files/tonality-analysis", content=json.dumps(payload))
        assert resp.status_code == 504
        data = resp.json()
        assert data["message"] == ResponseErrorMessage.TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_tonality_analysis_internal_error(app_base, monkeypatch):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceUserFileYes()

    async def _mock_send_message_to_sqs(queue_url, body):
        raise Exception("boom")

    monkeypatch.setattr("src.app.file_management.routers.send_message_to_sqs", _mock_send_message_to_sqs)

    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        payload = {"s3_key": "uuid_key_file.txt"}
        resp = await ac.post("/files/tonality-analysis", content=json.dumps(payload))
        assert resp.status_code == 500
        data = resp.json()
        assert data["detail"] == ResponseErrorMessage.INTERNAL_ERROR
