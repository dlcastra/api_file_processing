from decouple import config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from src.app.constants import SESSION_AGE
from src.app.file_management import router as fm_router
from src.app.webhooks import router as webhook_router
from src.app.auth import router as auth_router

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config("SECRET_KEY"), session_cookie="session_id", max_age=SESSION_AGE)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(fm_router, prefix="/files", tags=["FileProcessing"])
app.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = [{"field": err["loc"][-1], "msg": err["msg"]} for err in exc.errors()]
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.on_event("startup")
async def startup():
    from src.settings.database import engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
