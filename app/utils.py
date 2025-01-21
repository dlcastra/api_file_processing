from fastapi import HTTPException
from fastapi.requests import Request
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthUtils:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)


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


def get_current_user_from_session(request: Request):
    session_id = request.session.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id
