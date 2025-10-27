import json

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.requests import Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from src.app.auth.utils import blacklist_check
from src.app.aws.utils import send_message_to_sqs
from src.app.file_management.services import FileManagementService
from src.app.responses.generator import ResponseGeneratorService
from src.app.responses.statuses import ResponseErrorMessage
from src.app.validators.file_validation import FileValidator, invalid_file
from src.app.webhooks.utils import wait_for_cache
from src.settings.config import logger
from src.settings.config import settings
from src.settings.database import get_db

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
        logger.error(f"File History Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.post("/upload", dependencies=[Depends(blacklist_check)], status_code=201)
async def upload_file(
    request: Request, file: UploadFile = File(...), service: FileManagementService = Depends(get_file_manager)
):
    is_valid_file = FileValidator().validate_file(file)
    if not is_valid_file:
        logger.warning("File Upload Validation Error", exc_info=True)
        raise HTTPException(status_code=400, detail=invalid_file)

    try:
        user_id: int = request.session.get("user_id")
        return await service.add_file(file, user_id)
    except Exception as e:
        logger.error(f"File Upload Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.get("/download/{file_id}", dependencies=[Depends(blacklist_check)], status_code=200)
async def download_file(request: Request, file_id: int, service: FileManagementService = Depends(get_file_manager)):
    try:
        return await service.download_file(file_id, request.session.get("user_id"))
    except Exception as e:
        logger.error(f"File Download Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.delete("/remove/{file_id}", dependencies=[Depends(blacklist_check)], status_code=204)
async def remove_file(request: Request, file_id: int, service: FileManagementService = Depends(get_file_manager)):
    try:
        return await service.remove_file(file_id, request.session.get("user_id"))
    except Exception as e:
        logger.error(f"File Remove Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.post("/convert", dependencies=[Depends(blacklist_check)], status_code=201)
async def convert_file(
    request: ConvertFileRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")
    response_generator = ResponseGeneratorService(file_manager_service=service)

    try:
        # is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        # if not is_user_file:
        #     logger.warning(f"{ResponseErrorMessage.FILE_DOES_NOT_EXIST}, File key: {s3_key}")
        #     return JSONResponse(status_code=400, content={"message": ResponseErrorMessage.FILE_DOES_NOT_EXIST})

        request_body = request.model_dump()
        request_body["callback_url"] = settings.CONVERTER_WEBHOOK_URL
        request_body = json.dumps(request_body)

        message, is_sent = await send_message_to_sqs(settings.AWS_SQS_QUEUE_CONVERTER_URL, request_body)
        if not is_sent:
            logger.error(message)
            return JSONResponse(status_code=500, content={"message": message})

        cashed_data = await wait_for_cache(s3_key, "file_conversion")
        return await response_generator.generate_response(cashed_data, use_s3=True)

    except Exception as e:
        logger.error(f"File converter error: {e}")
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.post("/parse-file")
async def parse_file(
    request: FileParserRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")
    response_generator = ResponseGeneratorService()

    try:
        is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        if not is_user_file:
            logger.warning(f"{ResponseErrorMessage.FILE_DOES_NOT_EXIST}, File key: {s3_key}")
            return JSONResponse(status_code=400, content={"message": ResponseErrorMessage.FILE_DOES_NOT_EXIST})

        request_body = request.model_dump()
        request_body["callback_url"] = settings.FILE_PARSER_WEBHOOK_URL
        request_body = json.dumps(request_body)

        message, is_sent = await send_message_to_sqs(settings.AWS_SQS_QUEUE_CONVERTER_URL, request_body)
        if not is_sent:
            logger.error(message)
            return JSONResponse(status_code=500, content={"message": message})

        cashed_data = await wait_for_cache(s3_key, "file_parsing")
        logger.info(cashed_data)
        return await response_generator.generate_response(cashed_data)

    except Exception as e:
        logger.error(f"File parser error {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)


@router.post("/tonality-analysis", dependencies=[Depends(blacklist_check)], status_code=201)
async def process_tonality_analysis(
    request: FileTonalityAnalysisRequest, fapi_req: Request, service: FileManagementService = Depends(get_file_manager)
):
    s3_key = request.s3_key
    user_id = fapi_req.session.get("user_id")
    response_generator = ResponseGeneratorService()

    try:
        is_user_file = await service.check_user_file(s3_key=s3_key, user_id=user_id)
        if not is_user_file:
            logger.warning(f"{ResponseErrorMessage.FILE_DOES_NOT_EXIST}, File key: {s3_key}")
            return JSONResponse(status_code=400, content={"message": ResponseErrorMessage.FILE_DOES_NOT_EXIST})

        request_body = request.model_dump()
        request_body["callback_url"] = settings.ANALYSIS_WEBHOOK_URL
        request_body = json.dumps(request_body)

        message, is_sent = await send_message_to_sqs(settings.AWS_SQS_QUEUE_ANALYSIS_URL, request_body)
        if not is_sent:
            logger.error(message)
            return JSONResponse(status_code=500, content={"message": message})

        cashed_data = await wait_for_cache(s3_key, "tonality_analysis")
        return await response_generator.generate_response(cashed_data)

    except Exception as e:
        logger.error(f"File tonality analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=ResponseErrorMessage.INTERNAL_ERROR)
