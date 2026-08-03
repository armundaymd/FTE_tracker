from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ed_capacity"
    SECRET_KEY: str = "change_me_before_deploying"
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    model_config = {"env_file": (".env", "../.env"), "extra": "ignore"}


settings = Settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,          # set True to log SQL during development
    pool_pre_ping=True,  # recycle stale connections
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
