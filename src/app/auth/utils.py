from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.requests import Request
from jose import jwt
from passlib.context import CryptContext

from src.app.constants import SESSION_AGE
from src.settings.config import settings, redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthUtils:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token() -> str:
        expire = datetime.now() + timedelta(seconds=SESSION_AGE)
        return jwt.encode({"exp": expire}, settings.SECRET_KEY, algorithm="HS256")


def get_current_user_from_session(request: Request):
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id


async def store_session(redis, user_id, session_id):
    key = f"user:{user_id}:session:{session_id}"
    await redis.set(key, "active", ex=SESSION_AGE)


async def add_to_blacklist(redis_url, session_ids: list[str]) -> None:
    for session_id in session_ids:
        key = f"blacklist:session:{session_id}"
        await redis_url.set(key, "1", ex=SESSION_AGE)


async def blacklist_check(request: Request) -> None:
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    key = f"blacklist:session:{session_id}"
    is_blacklisted = await redis.exists(key)
    if is_blacklisted:
        request.session.clear()
        await redis.delete(key)
