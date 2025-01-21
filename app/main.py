from decouple import config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config("SECRET_KEY"), session_cookie="session_id", max_age=30)
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    errors = [{"field": err["loc"][-1], "msg": err["msg"]} for err in exc.errors()]
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors},
    )


@app.on_event("startup")
async def startup():
    from settings.database import engine, Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
