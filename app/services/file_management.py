import uuid

from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File as FileModel
from settings.aws_config import s3_client
from settings.config import settings


class FileManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.s3_client = s3_client
        self.bucket = settings.AWS_S3_BUCKET_NAME
        self.region = settings.AWS_REGION

    async def get_files_history(self, user_id: int):
        user_files = await self.db.execute(select(FileModel).filter_by(user_id=user_id))
        files = user_files.scalars().all()

        if not files:
            return {"detail": "The files have not been uploaded yet"}

        return files

    async def add_file(self, file, user_id: int):
        file_content = await file.read()
        original_file_name = file.filename

        s3_file_name = f"{str(uuid.uuid4())}_{original_file_name}"
        file_url = await self._upload_to_s3(s3_file_name, file_content)

        if file_url["status"] == "success":
            new_file = FileModel(
                file_name=original_file_name,
                s3_url=file_url["file_url"],
                s3_key=s3_file_name,
                user_id=user_id,
            )
            self.db.add(new_file)
            await self.db.commit()

            return new_file

        return file_url

    async def download_file(self, file_id: int, user_id: int):
        stmt = select(FileModel).filter(FileModel.id == file_id, FileModel.user_id == user_id)
        result = await self.db.execute(stmt)
        file: FileModel = result.scalar_one_or_none()

        if not file:
            raise HTTPException(status_code=404, detail="File does not exist")

        try:
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": file.s3_key},
                ExpiresIn=1800,
            )
            return {"file_url": presigned_url}

        except NoCredentialsError:
            return {"status": "error", "message": "AWS credentials not found"}
        except PartialCredentialsError:
            return {"status": "error", "message": "Incomplete AWS credentials"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def remove_file(self, file_id: int, user_id: int):
        stmt = select(FileModel).filter(FileModel.id == file_id, FileModel.user_id == user_id)
        result = await self.db.execute(stmt)
        file: FileModel = result.scalar_one_or_none()

        if not file:
            raise HTTPException(status_code=404, detail="File does not exist")

        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=file.s3_key)
        except NoCredentialsError:
            return {"status": "error", "message": "AWS credentials not found"}
        except PartialCredentialsError:
            return {"status": "error", "message": "Incomplete AWS credentials"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

        try:
            await self.db.delete(file)
            await self.db.commit()
            return {"detail": "File deleted successfully"}
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Failed to delete file from database")

    async def check_user_file(self, s3_key: str, user_id: int) -> bool:
        stmt = select(FileModel).filter(FileModel.s3_key == s3_key, FileModel.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_file_by_uuid(self, s3_key: str) -> FileModel | None:
        file_uuid_code = s3_key.split("_")[0]
        stmt = select(FileModel).filter(FileModel.s3_key.startswith(file_uuid_code))
        result = await self.db.execute(stmt)
        file: FileModel = result.scalar_one_or_none()

        return file

    async def _upload_to_s3(self, file_name: str, file_content: bytes):
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=file_name, Body=file_content)

            file_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{file_name}"
            return {"status": "success", "file_url": file_url}

        except NoCredentialsError:
            return {"status": "error", "message": "AWS credentials not found"}
        except PartialCredentialsError:
            return {"status": "error", "message": "Incomplete AWS credentials"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
