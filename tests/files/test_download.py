import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from starlette.middleware.sessions import SessionMiddleware

from src.app.file_management.routers import router as files_router, get_file_manager
from src.app.auth.utils import blacklist_check
from src.app.responses.statuses import ResponseErrorMessage


class StubFileManagementServiceSuccess:
    async def download_file(self, file_id: int, user_id: int):
        return {"file_url": f"https://bucket.s3.region.amazonaws.com/presigned/{file_id}"}


class StubFileManagementServiceNotFound:
    async def download_file(self, file_id: int, user_id: int):
        # Mimic service returning JSONResponse(404) when file does not exist
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=404, content={"message": ResponseErrorMessage.FILE_DOES_NOT_EXIST})


class StubFileManagementServiceError:
    async def download_file(self, file_id: int, user_id: int):
        # Cause router to catch and return 500 INTERNAL_ERROR
        raise Exception("Unexpected failure")


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
async def test_download_success(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceSuccess()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.get("/files/download/1")
        assert resp.status_code == 200
        data = resp.json()
        assert "file_url" in data
        assert data["file_url"].startswith("https://")


@pytest.mark.asyncio
async def test_download_not_found(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceNotFound()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.get("/files/download/999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["message"] == ResponseErrorMessage.FILE_DOES_NOT_EXIST


@pytest.mark.asyncio
async def test_download_internal_error(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceError()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.get("/files/download/2")
        assert resp.status_code == 500
        data = resp.json()
        assert data["detail"] == ResponseErrorMessage.INTERNAL_ERROR
