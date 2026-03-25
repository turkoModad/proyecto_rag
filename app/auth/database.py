from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import ADMIN_DATABASE_URL, USER_DATABASE_URL


# =========================
# ENGINES
# =========================
engine = create_async_engine(
    USER_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_timeout=60,
    pool_recycle=1800
)

admin_engine = create_async_engine(
    ADMIN_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=60,
    pool_recycle=1800
)


# =========================
# SESSIONMAKERS
# =========================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

AdminSessionLocal = async_sessionmaker(
    bind=admin_engine,
    expire_on_commit=False
)


# =========================
# BASE
# =========================
Base = declarative_base()


# =========================
# DEPENDENCIES
# =========================
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def get_admin_db():
    async with AdminSessionLocal() as session:
        yield session