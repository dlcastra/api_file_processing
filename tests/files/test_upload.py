import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from starlette.middleware.sessions import SessionMiddleware

from src.app.file_management.routers import router as files_router, get_file_manager
from src.app.auth.utils import blacklist_check
from src.app.validators.file_validation import FileValidator


class StubFileManagementService:
    async def get_files_history(self, user_id: int):
        return {"detail": "The files have not been uploaded yet"}


class StubFileManagementServiceWithFiles:
    async def get_files_history(self, user_id: int):
        return [
            {
                "id": 1,
                "file_name": "doc.txt",
                "s3_url": "https://bucket.s3.region.amazonaws.com/uuid_doc.txt",
                "s3_key": "uuid_doc.txt",
                "user_id": user_id,
            }
        ]


class StubFileManagementServiceForUpload:
    async def add_file(self, file, user_id: int):
        return {
            "id": 1,
            "file_name": file.filename,
            "s3_url": f"https://bucket.s3.region.amazonaws.com/{file.filename}",
            "s3_key": file.filename,
            "user_id": user_id,
        }


async def _noop_blacklist_check():
    return True


@pytest_asyncio.fixture
async def app_base():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
    app.include_router(files_router, prefix="/files")
    app.dependency_overrides[blacklist_check] = _noop_blacklist_check
    return app


@pytest_asyncio.fixture
async def client_empty_history(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementService()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_with_files(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceWithFiles()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_upload_success(app_base):
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceForUpload()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_files_history_empty(client_empty_history):
    resp = await client_empty_history.get("/files/storage")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"detail": "The files have not been uploaded yet"}


@pytest.mark.asyncio
async def test_files_history_with_items(client_with_files):
    resp = await client_with_files.get("/files/storage")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["file_name"] == "doc.txt"


@pytest.mark.asyncio
async def test_upload_success(client_upload_success):
    content = b"hello world"
    files = {"file": ("doc.txt", content, "text/plain")}
    resp = await client_upload_success.post("/files/upload", files=files)
    assert resp.status_code == 201
    data = resp.json()
    assert data["file_name"] == "doc.txt"


@pytest.mark.asyncio
async def test_upload_invalid_file(monkeypatch, app_base):
    monkeypatch.setattr(FileValidator, "validate_file", lambda self, f: False)
    app_base.dependency_overrides[get_file_manager] = lambda: StubFileManagementServiceForUpload()
    async with AsyncClient(transport=ASGITransport(app=app_base), base_url="http://test") as ac:
        content = b"bad file"
        files = {"file": ("doc.exe", content, "application/octet-stream")}
        resp = await ac.post("/files/upload", files=files)
        assert resp.status_code == 400
        data = resp.json()
        assert "supported_formats" in data["detail"]
