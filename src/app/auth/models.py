import re

from pydantic import BaseModel, EmailStr, field_validator, model_validator
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.settings.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    totp_secret = Column(String, unique=True, default="")
    is_2fa_enabled = Column(Boolean, default=False)

    files = relationship("src.app.file_management.models.File", back_populates="owner")


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    password1: str

    @field_validator("username")
    def validate_username(cls, username):
        if len(username) < 5:
            raise ValueError("Username must be at least 5 characters long")
        if len(username) > 100:
            raise ValueError("Username cannot contain more than 100 characters")
        if " " in username:
            raise ValueError("Username cannot contain spaces")
        if re.search(r"[;\'\"\-\-]", username):
            raise ValueError("Username contains forbidden characters")

        return username

    @model_validator(mode="after")
    def validate_password(self):
        if self.password != self.password1:
            raise ValueError("The passwords must match")

        return self


class UserLogin(BaseModel):
    username: str
    password: str
    totp_code: str | None
