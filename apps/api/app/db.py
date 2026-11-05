from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker,AsyncSession
from app.config import settings
engine=create_async_engine(settings.database_url,pool_pre_ping=True,pool_size=15,max_overflow=25)
SessionLocal=async_sessionmaker(engine,expire_on_commit=False,class_=AsyncSession)
async def get_db():
    async with SessionLocal() as db: yield db
