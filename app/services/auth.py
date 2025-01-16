from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, AuthToken
from app.utils import AuthUtils


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_util = AuthUtils()

    async def register_user(self, user_data):
        existing_user = await self.db.execute(select(User).filter(User.email == user_data["email"]))
        existing_user = existing_user.scalars().first()

        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

        hashed_password = self.auth_util.hash_password(user_data["password"])
        new_user = User(username=user_data["username"], email=user_data["email"], password=hashed_password)

        self.db.add(new_user)
        try:
            await self.db.commit()
            return new_user
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create user")

    async def authenticate_user(self, username: str, password: str):
        user = await self.db.execute(select(User).filter(User.username == username))
        user = user.scalars().first()

        if not user:
            return None

        if not self.auth_util.verify_password(password, user.password):
            return None

        return user

    async def save_auth_token(self, user: User, token_key: str) -> AuthToken:
        auth_token = AuthToken(user_id=user.id, key=token_key)

        self.db.add(auth_token)
        try:
            await self.db.commit()
            return auth_token
        except Exception:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail="Failed to create auth token")

    async def remove_auth_token(self, key: str):
        try:
            query = select(AuthToken).filter(AuthToken.key == key)
            result = await self.db.execute(query)
            token = result.scalars().first()

            if token:
                await self.db.delete(token)
                await self.db.commit()
            else:
                raise HTTPException(status_code=404, detail="Token not found")
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Error removing token: {str(e)}")
