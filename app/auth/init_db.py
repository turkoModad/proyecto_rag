import logging
from sqlalchemy import text
from app.auth.database import engine, admin_engine, Base
from app.core.config import DB_NAME
from app.auth import models


logger = logging.getLogger("DBInit")


async def create_database_if_not_exists():
    async with admin_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
            {"dbname": DB_NAME}
        )
        exists = result.scalar()

        if not exists:
            await conn.execute(text("COMMIT"))
            await conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))



async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db_connections():
    await engine.dispose()
    await admin_engine.dispose()
