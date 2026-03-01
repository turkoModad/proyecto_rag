# from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
# from sqlalchemy.orm import declarative_base
# from app.core.config import ADMIN_DATABASE_URL, USER_DATABASE_URL


# engine = create_async_engine(
#     USER_DATABASE_URL,
#     echo=False,
#     pool_pre_ping=True
# )

# admin_engine = create_async_engine(
#     ADMIN_DATABASE_URL,
#     echo=False,
#     pool_pre_ping=True
# )

# AsyncSessionLocal = async_sessionmaker(
#     bind=engine,
#     expire_on_commit=False
# )

# Base = declarative_base()


























from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import ADMIN_DATABASE_URL, USER_DATABASE_URL


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

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()