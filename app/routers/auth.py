import uuid
from base64 import b64encode
from datetime import datetime
from io import BytesIO

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserCreate, UserLogin, User
from app.services.auth import AuthService, store_session
from app.utils import add_to_blacklist, blacklist_check
from app.validators.password_validation import PasswordValidator, invalid_password
from settings.config import redis, templates
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

    user: User = await auth_service.authenticate_user(user_data.username, user_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if user.is_2fa_enabled:
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(user_data.totp_code):
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    user.last_login = datetime.now()
    db.add(user)
    await db.commit()
    await db.refresh(user)

    session_id = str(uuid.uuid4())
    request.session["session_id"] = session_id
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


@router.post("/enable-2fa", status_code=201, dependencies=[Depends(blacklist_check)])
async def enable_2fa(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")

    try:
        user = await db.get(User, user_id)

        user.totp_secret = pyotp.random_base32()
        user.is_2fa_enabled = True
        await db.commit()

        totp_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(name=user.username, issuer_name="FPMA")
        qr = qrcode.make(totp_uri)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qrcode_base64 = b64encode(buffer.getvalue()).decode()

        return templates.TemplateResponse("totp.html", {"request": request, "qr_code": qrcode_base64})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable-2fa", status_code=200, dependencies=[Depends(blacklist_check)])
async def disable_2fa(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    try:
        user = await db.get(User, user_id)

        user.totp_secret = "disabled"
        user.is_2fa_enabled = False
        await db.commit()

        return {"message": "Successfully disabled 2FA"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
