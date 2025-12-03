import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from starlette.middleware.sessions import SessionMiddleware

from src.app.file_management.routers import router as files_router, get_file_manager
from src.app.auth.utils import blacklist_check
from src.app.responses.statuses import ResponseErrorMessage


class StubFileManagementServiceRemoveSuccess:
    async def remove_file(self, file_id: int, user_id: int):
        return {"detail": "File deleted successfully"}


class StubFileManagementServiceRemoveNotFound:
    async def remove_file(self, file_id: int, user_id: int):
        from starlette.responses import JSONResponse

        return JSONResponse(status_code=404, content={"message": "File does not exist"})


class StubFileManagementServiceRemoveError:
    async def remove_file(self, file_id: int, user_id: int):
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
async def test_remove_success(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceRemoveSuccess()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.delete("/files/remove/1")
        assert resp.status_code == 204
        # Some clients may not include body for 204; ensure no error on parsing
        if resp.content:
            data = resp.json()
            assert data.get("detail") == "File deleted successfully"


@pytest.mark.asyncio
async def test_remove_not_found(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceRemoveNotFound()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.delete("/files/remove/999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["message"] == "File does not exist"


@pytest.mark.asyncio
async def test_remove_internal_error(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceRemoveError()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        resp = await ac.delete("/files/remove/2")
        assert resp.status_code == 500
        data = resp.json()
        assert data["detail"] == ResponseErrorMessage.INTERNAL_ERROR
