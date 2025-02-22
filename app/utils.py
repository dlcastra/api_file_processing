import asyncio
import json
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict

from fastapi import HTTPException
from fastapi.requests import Request
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import SESSION_AGE
from app.models.statuses import ResponseErrorMessage
from settings.aws_config import sqs_client
from settings.config import settings, redis

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Sync
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


# Async
async def async_get_or_create(session: AsyncSession, model, defaults=None, **kwargs):
    stmt = select(model).filter_by(**kwargs)
    result = await session.execute(stmt)
    instance = result.scalars().first()

    if instance:
        return instance, False

    kwargs |= defaults or {}
    instance = model(**kwargs)

    try:
        session.add(instance)
        await session.commit()
        return instance, True

    except IntegrityError:
        await session.rollback()
        result = await session.execute(stmt)
        instance = result.scalars().first()

        return instance, False


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


async def wait_for_cache(s3_key: str, timeout: int = 30, interval: float = 0.2) -> dict | None:
    """Waits for the result to appear in the cache with timeout"""
    uuid_key = s3_key.split("_")[0]
    cache_key = f"tonality_status:{uuid_key}"
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) < timeout:
        status_data = await redis.get(cache_key)
        if status_data:
            try:
                return json.loads(status_data)
            except json.JSONDecodeError:
                raise {"message": "Invalid data in cache"}
        await asyncio.sleep(interval)

    return None


async def send_message_to_sqs(request_body: str) -> Tuple[Optional[Dict[str, str | bool]], bool]:
    response = sqs_client.send_message(QueueUrl=settings.AWS_SQS_QUEUE_URL, MessageBody=request_body)
    status_code = response["ResponseMetadata"]["HTTPStatusCode"]
    if status_code != 200:
        return {"success": False, "message": ResponseErrorMessage.QUEUE_ERROR}, False
    elif "MessageId" not in response:
        return {"success": False, "message": ResponseErrorMessage.SQS_ENQUEUE_TASK_ERROR}, False
    return None, True


async def check_cache(redis_url):
    """Never use in production"""
    keys = await redis_url.keys("*")
    print("Keys in cache:", keys)
