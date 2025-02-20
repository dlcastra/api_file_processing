import json

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_management import FileManagementService
from app.utils import blacklist_check, wait_for_cache
from app.validators.file_validation import FileValidator, invalid_file
from settings.aws_config import sqs_client
from settings.config import settings
from settings.database import get_db

router = APIRouter()


class ConvertFileRequest(BaseModel):
    s3_key: str
    format_from: str
    format_to: str


class FileTonalityAnalysisRequest(BaseModel):
    s3_key: str


class FileParserRequest(BaseModel):
    s3_key: str
    keywords: list[str]


async def get_file_manager(db: AsyncSession = Depends(get_db)) -> FileManagementService:
    return FileManagementService(db)


@router.get("/storage", dependencies=[Depends(blacklist_check)], status_code=200)
async def files_history(request: Request, service: FileManagementService = Depends(get_file_manager)):
    try:
        return await service.get_files_history(request.session.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", dependencies=[Depends(blacklist_check)], status_code=201)
async def upload_file(
    request: Request, file: UploadFile = File(...), service: FileManagementService = Depends(get_file_manager)
):
    is_valid_file = FileValidator().validate_file(file)
    if not is_valid_file:
        raise HTTPException(status_code=400, detail=invalid_file)

    try:
        user_id: int = request.session.get("user_id")
        return await service.add_file(file, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{file_id}", dependencies=[Depends(blacklist_check)], status_code=200)
async def download_file(request: Request, file_id: int, service: FileManagementService = Depends(get_file_manager)):
    try:
        return await service.download_file(file_id, request.session.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/remove/{file_id}", dependencies=[Depends(blacklist_check)], status_code=204)
async def remove_file(request: Request, file_id: int, service: FileManagementService = Depends(get_file_manager)):
    try:
        return await service.remove_file(file_id, request.session.get("user_id"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert", dependencies=[Depends(blacklist_check)], status_code=201)
async def convert_file(
    request: ConvertFileRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")

    try:
        is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        if not is_user_file:
            raise HTTPException(status_code=400, detail="File does not exist")

        request_body = request.dict()
        request_body["callback_url"] = settings.CONVERTER_WEBHOOK_URL
        request_body = json.dumps(request_body)

        response = sqs_client.send_message(QueueUrl=settings.AWS_SQS_QUEUE_URL, MessageBody=request_body)

        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            return {"success": False, "message": "Error while converting file"}

        key_in_cache = await wait_for_cache(s3_key)
        if key_in_cache:
            file = await service.find_file_by_uuid(s3_key)
            result = await service.download_file(file.id, user_id)
            result["success"] = True
            return result
        return {"success": False, "message": "Timeout while waiting for analysis result"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/parse-file")
async def parse_file(
    request: FileParserRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")

    try:
        is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        if not is_user_file:
            raise HTTPException(status_code=400, detail="File does not exist")

        request_body = request.dict()
        request_body["callback_url"] = settings.FILE_PARSER_WEBHOOK_URL
        request_body = json.dumps(request_body)

        response = sqs_client.send_message(QueueUrl=settings.AWS_SQS_QUEUE_URL, MessageBody=request_body)
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            return {"success": False, "message": "Error while parsing file"}

        result = await wait_for_cache(s3_key)
        if result:
            result["status"] = True
            return result

        return {"success": False, "message": "Timeout while waiting for analysis result"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tonality-analysis", dependencies=[Depends(blacklist_check)], status_code=201)
async def process_tonality_analysis(
    request: FileTonalityAnalysisRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")
    try:
        is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        if not is_user_file:
            raise HTTPException(status_code=400, detail="File does not exist")

        request_body = request.dict()
        request_body["callback_url"] = settings.ANALYSIS_WEBHOOK_URL
        request_body = json.dumps(request_body)

        response = sqs_client.send_message(QueueUrl=settings.AWS_SQS_QUEUE_URL, MessageBody=request_body)
        if response["ResponseMetadata"]["HTTPStatusCode"] != 200:
            return {"success": False, "message": "Error while sending message to the queue"}

        result = await wait_for_cache(s3_key)
        if result:
            result["status"] = True
            return result

        return {"success": False, "message": "Timeout while waiting for analysis result"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
