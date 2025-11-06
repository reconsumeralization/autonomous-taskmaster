from sqlalchemy.ext.asyncio import create_async_engine
from mission_knowledge_nexus.app.models import Base
import asyncio

DATABASE_URL = "postgresql+asyncpg://nexus_user:nexus_password@localhost:5432/nexus_db"

async def create_db_tables():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(create_db_tables())
