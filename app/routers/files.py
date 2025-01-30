from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_management import FileManagementService
from app.utils import blacklist_check
from settings.database import get_db
from app.validators.file_validation import FileValidator, invalid_file

router = APIRouter()


@router.get("/history", dependencies=[Depends(blacklist_check)], status_code=200)
async def files_history(request: Request, db: AsyncSession = Depends(get_db)):
    file_manager = FileManagementService(db)
    return await file_manager.get_files_history(request.session.get("user_id"))


@router.post("/upload", dependencies=[Depends(blacklist_check)], status_code=201)
async def upload_file(request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    is_valid_file = FileValidator().validate_file(file)
    if not is_valid_file:
        raise HTTPException(status_code=400, detail=invalid_file)

    file_manager = FileManagementService(db)
    user_id: int = request.session.get("user_id")

    return await file_manager.add_file(file, user_id)


@router.get("/download/{file_id}", dependencies=[Depends(blacklist_check)], status_code=200)
async def download_file(request: Request, file_id: int, db: AsyncSession = Depends(get_db)):
    file_manager = FileManagementService(db)
    return await file_manager.download_file(file_id, request.session.get("user_id"))


@router.delete("/remove/{file_id}", dependencies=[Depends(blacklist_check)], status_code=204)
async def remove_file(request: Request, file_id: int, db: AsyncSession = Depends(get_db)):
    file_manager = FileManagementService(db)
    return await file_manager.remove_file(file_id, request.session.get("user_id"))
