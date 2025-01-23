import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserCreate, UserLogin
from app.services.auth import AuthService, store_session
from app.utils import get_current_user_from_session, AuthUtils, add_to_blacklist, blacklist_check
from app.validation.password_validation import PasswordValidator, invalid_password
from settings.config import redis
from settings.database import get_db

router = APIRouter()


class RegistrationResponse(BaseModel):
    message: str = "Registration successfully completed"


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
        print(f"{new_user.id} -- {new_user.username}")

        return RegistrationResponse()

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error during registration: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/login", status_code=201)
async def login(request: Request, user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    auth_service = AuthService(db)
    auth_util = AuthUtils()

    user = await auth_service.authenticate_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_id = str(uuid.uuid4())
    request.session["session_id"] = session_id
    request.session["access_token"] = {"type": "Bearer", "access_token": auth_util.create_access_token()}
    request.session["user_id"] = user.id

    await store_session(redis, user.id, session_id)

    return {"message": "Login successful"}


@router.post("/logout", status_code=200)
async def logout(request: Request):
    user_id = request.session.get("user_id")
    session_id = request.session.get("session_id")
    if not session_id or not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    request.session.clear()
    await redis.delete(f"user:{user_id}:session:{session_id}")

    return {"message": "Logout successful"}


@router.post("/logout-others", status_code=200, dependencies=[Depends(blacklist_check)])
async def logout_others(request: Request):
    user_id = request.session.get("user_id")
    session_id = request.session.get("session_id")
    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    keys = await redis.keys(f"user:{user_id}:session:*")
    keys_to_delete = [key.decode("utf-8") for key in keys if not key.decode("utf-8").endswith(session_id)]
    session_ids = [key.split(":")[-1] for key in keys_to_delete]

    if keys_to_delete:
        await add_to_blacklist(redis, session_ids)
        await redis.delete(*keys_to_delete)
        return {"message": "Logout others successfully", "count": f"{len(keys_to_delete)}"}

    return {"message": "No external sessions"}


@router.get("/protected", dependencies=[Depends(blacklist_check)])
async def protected_route(session_id: str = Depends(get_current_user_from_session)):
    return {"message": "You are authenticated", "session_id": session_id}
