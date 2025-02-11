import httpx
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_management import FileManagementService
from app.utils import blacklist_check
from settings.config import settings
from settings.database import get_db
from app.validators.file_validation import FileValidator, invalid_file
from app.models.file import File as FileModel

router = APIRouter()


class ConvertFileRequest(BaseModel):
    s3_key: str
    format_from: str
    format_to: str


class FileConverterResponse(BaseModel):
    file_url: str
    new_s3_key: str
    status: str


@router.get("/storage", dependencies=[Depends(blacklist_check)], status_code=200)
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


@router.post("/convert", dependencies=[Depends(blacklist_check)], status_code=201)
async def convert_file(request: ConvertFileRequest, fapi_req: Request, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        try:
            request_body = {
                "s3_key": request.s3_key,
                "format_from": request.format_from,
                "format_to": request.format_to,
                "callback_url": settings.INTERNAL_WEBHOOK_URL,
            }
            response = await client.post(settings.FILE_CONVERTER_URL, json=request_body)
            response.raise_for_status()

            if response.json()["status"] == "success":
                file_manager = FileManagementService(db)

                file_uuid_code = request.s3_key.split("_")[0]
                stmt = select(FileModel).filter(FileModel.s3_key.startswith(file_uuid_code))
                result = await db.execute(stmt)
                file: FileModel = result.scalar_one_or_none()

                result = await file_manager.download_file(file.id, fapi_req.session.get("user_id"))
                result["success"] = True

                return result

            return {"success": False, "message": "Error while converting file"}

        except httpx.HTTPError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/converter-webhook")
async def convert_webhook(request: FileConverterResponse, db: AsyncSession = Depends(get_db)):
    if request.status == "success":
        file_uuid_code = request.new_s3_key.split("_")[0]
        stmt = select(FileModel).filter(FileModel.s3_key.startswith(file_uuid_code))
        result = await db.execute(stmt)
        file: FileModel = result.scalar_one_or_none()

        if not file:
            return {"error": "File not found"}

        file.s3_url = request.file_url
        file.s3_key = request.new_s3_key

        await db.commit()
        return {"message": "File updated successfully"}
