# init_db.py
import asyncio
from app.db.session import engine, Base
from app.models.knowledge_db import *  # Imports the models to register them with Base

async def init_models():
    async with engine.begin() as conn:
        print("Creating MySQL tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Done!")

if __name__ == "__main__":
    asyncio.run(init_models())