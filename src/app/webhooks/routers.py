import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.file_management.services import FileManagementService
from src.settings.config import redis
from src.settings.database import get_db

router = APIRouter()


class FileConverterResponse(BaseModel):
    file_url: str
    new_s3_key: str
    status: str


class FileParserResponse(BaseModel):
    count: int
    sentences: list[str]
    s3_key: str
    status: str


class FileTonalityAnalysisResponse(BaseModel):
    s3_key: str
    polarity: float
    subjectivity: float
    objective_sentiment_score: float
    polarity_status: str
    polarity_description: str
    subjectivity_status: str
    subjectivity_description: str
    objective_sentiment_status: str
    objective_sentiment_description: str
    status: str


@router.post("/converter-webhook")
async def convert_webhook(request: FileConverterResponse, db: AsyncSession = Depends(get_db)):
    service = FileManagementService(db)
    await add_response_data_to_cache(request.new_s3_key, request.dict())

    if request.status == "success":
        file = await service.find_file_by_uuid(s3_key=request.new_s3_key)
        if not file:
            return {"error": "File not found"}

        file.s3_url = request.file_url
        file.s3_key = request.new_s3_key

        await db.commit()
        return {"message": "File updated successfully"}

    return None


@router.post("/parser-webhook")
async def parser_webhook(request: FileParserResponse):
    await add_response_data_to_cache(request.s3_key, request.dict())

    if request.status == "success":
        return {"message": "Parsing result cached"}
    return None


@router.post("/analysis-webhook")
async def analysis_webhook(request: FileTonalityAnalysisResponse):
    await add_response_data_to_cache(request.s3_key, request.dict())

    if request.status == "success":
        return {"message": "Tonality analysis result cached"}
    return None


async def add_response_data_to_cache(s3_key, data):
    uuid_key = s3_key.split("_")[0]
    cache_key = f"tonality_status:{uuid_key}"
    await redis.setex(cache_key, 60, json.dumps(data))
