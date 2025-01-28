from fastapi import APIRouter, Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from settings.database import get_db

router = APIRouter()


@router.get("/history", status_code=200)
async def files_history(request: Request): ...


@router.post("/upload", status_code=201)
async def upload_file(request: Request): ...


@router.get("/download/{file_id}", status_code=200)
async def download_file(file_id: str, db: AsyncSession = Depends(get_db())): ...


@router.delete("/remove/{file_id}", status_code=204)
async def remove_file(file_id: str, db: AsyncSession = Depends(get_db())): ...
