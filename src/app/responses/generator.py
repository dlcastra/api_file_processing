from starlette.responses import JSONResponse

from src.app.responses.statuses import ResponseErrorMessage, ProcessingStatus


class ResponseGeneratorService:
    def __init__(self, file_manager_service=None):
        self._data = {}
        self._file_manager_service = file_manager_service

    async def generate_response(self, data: dict, use_s3: bool = False):
        if data is None:
            return JSONResponse(status_code=504, content={"message": ResponseErrorMessage.TIMEOUT_ERROR})

        self._data = data
        return await self._generate_response(use_s3)

    async def _generate_response(self, use_s3: bool):
        status = self._data.get("status")
        if use_s3 and status == ProcessingStatus.SUCCESS:
            return await self._generate_with_s3_response()
        elif not use_s3 and status == ProcessingStatus.SUCCESS:
            return await self._no_s3_success_response()
        elif status == ProcessingStatus.ERROR:
            return await self._error_response()

        return {"message": ResponseErrorMessage.INTERNAL_ERROR}

    async def _generate_with_s3_response(self):
        s3_key = self._data.get("s3_key")
        return await self._file_manager_service.download_file(s3_key=s3_key)

    async def _no_s3_success_response(self):
        return self._data

    async def _error_response(self):
        return {"message": ResponseErrorMessage.FILE_PROCESSING_ERROR}
