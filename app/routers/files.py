from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from settings.aws_config import s3_client
from settings.config import settings
from settings.database import get_db

router = APIRouter()


#
@router.get("/history", status_code=200)
async def files_history(request: Request, db: AsyncSession = Depends(get_db)):
    return {}


@router.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...)):
    try:
        file_content = await file.read()
        file_name = file.filename
        bucket_name = settings.AWS_S3_BUCKET_NAME

        s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=file_content)
        file_url = f"https://{bucket_name}.s3.{s3_client.meta.region_name}.amazonaws.com/{file_name}"

        return {"status": "success", "file_url": file_url}

    except NoCredentialsError:
        return {"status": "error", "message": "AWS credentials not found"}
    except PartialCredentialsError:
        return {"status": "error", "message": "Incomplete AWS credentials"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/download/{file_id}", status_code=200)
async def download_file(file_id: str, db: AsyncSession = Depends(get_db)):
    return {}


@router.delete("/remove/{file_id}", status_code=204)
async def remove_file(file_id: str, db: AsyncSession = Depends(get_db)):
    return {}
