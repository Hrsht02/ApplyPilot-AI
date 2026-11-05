from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import engine
from app.models import Base
from app.auth import router as auth
from app.routes import router
from app.config import settings
@asynccontextmanager
async def lifespan(app:FastAPI):
    if settings.app_env=="development":
        async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
app=FastAPI(title="ApplyPilot AI API",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[settings.app_base_url],allow_credentials=True,allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["Content-Type","Authorization","X-User-Id"])
app.include_router(auth,prefix="/api"); app.include_router(router,prefix="/api")
@app.get("/health/live")
async def live(): return {"status":"ok"}
