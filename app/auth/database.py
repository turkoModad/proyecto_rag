from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import ADMIN_DATABASE_URL, USER_DATABASE_URL


engine = create_async_engine(
    USER_DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

admin_engine = create_async_engine(
    ADMIN_DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()