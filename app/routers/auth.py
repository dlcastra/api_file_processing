import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserCreate, UserLogin
from app.services.auth import AuthService
from app.utils import get_current_user_from_session
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


@router.post("/registration", response_model=RegistrationResponse, status_code=201)
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


@router.post("/login", status_code=201)
async def login(request: Request, user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)

    user = await auth_service.authenticate_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_id = str(uuid.uuid4())
    request.session["session_id"] = session_id
    request.session["user_id"] = user.id

    return {"message": "Login successful"}


@router.post("/logout", status_code=200)
async def logout(request: Request):
    session_id = request.session["session_id"]
    user_id = request.session["user_id"]
    if not session_id or not user_id:
        return HTTPException(status_code=401, detail="Not authenticated")

    request.session.clear()
    return {"message": "Logout successful"}


@router.get("/protected")
async def protected_route(session_id: str = Depends(get_current_user_from_session)):
    return {"message": "You are authenticated", "session_id": session_id}
