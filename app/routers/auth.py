from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserCreate, UserLogin, AuthToken
from app.services.auth import AuthService
from app.utils import AuthUtils, async_get_or_create
from app.validation.password_validation import PasswordValidator, invalid_password
from settings.database import get_db

router = APIRouter()


class RegistrationResponse(BaseModel):
    message: str = "Registration successfully completed"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"


class LogoutResponse(BaseModel):
    message: str = "Session logged out"


@router.post("/register", response_model=RegistrationResponse, status_code=201)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    psw_validator = PasswordValidator()

    try:
        is_valid_psw = psw_validator.password_validator(user_data.dict())
        if not is_valid_psw:
            raise HTTPException(status_code=400, detail=invalid_password)

        new_user = await auth_service.register_user(user_data.dict())
        print(new_user)

        return RegistrationResponse()

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error during registration: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login")
async def login(request: Request, user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    auth_utils = AuthUtils()

    try:
        user = await auth_service.authenticate_user(user_data.username, user_data.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token_data = {"sub": user.email, "id": user.id}
        access_token = auth_utils.create_access_token(data=token_data)
        user_agent = request.headers.get("User-Agent")
        token, created = await async_get_or_create(
            db,
            AuthToken,
            defaults={"user_id": user.id, "key": access_token, "user_agent": user_agent},
            user_id=user.id,
        )

        status_code = 201 if created else 200
        return JSONResponse(
            status_code=status_code,
            content={"access_token": token.key, "token_type": "Bearer"},
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error during registration: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/logout", response_model=LogoutResponse, status_code=200)
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    try:
        token = auth_header.split(" ")[1]
    except IndexError:
        raise HTTPException(status_code=400, detail="Invalid authorization header format")

    await auth_service.remove_auth_token(token)

    return RegistrationResponse
