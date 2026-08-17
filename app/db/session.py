import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Gracefully pull from settings if mapped, otherwise directly from the environment
MYSQL_USER = getattr(settings, "MYSQL_USER", os.getenv("MYSQL_USER", "root"))
MYSQL_PASSWORD = getattr(settings, "MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "root@123"))
MYSQL_HOST = getattr(settings, "MYSQL_HOST", os.getenv("MYSQL_HOST", "localhost"))
MYSQL_PORT = getattr(settings, "MYSQL_PORT", os.getenv("MYSQL_PORT", "3306"))
MYSQL_DB = getattr(settings, "MYSQL_DB", os.getenv("MYSQL_DB", "sensory_platform"))

# Construct the Async MySQL URL
DATABASE_URL = f"mysql+aiomysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# Create the Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # Set to True to see raw SQL queries in your console
    pool_pre_ping=True,  # Keeps connections alive
    pool_size=10,
    max_overflow=20
)

# Create the Session Factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# This is the Base that all our database models will inherit from
Base = declarative_base()

# FastAPI Dependency
async def get_db_session():
    """Yields a database session for a FastAPI request."""
    async with AsyncSessionLocal() as session:
        yield session