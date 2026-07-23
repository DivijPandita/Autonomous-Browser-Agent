from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as tasks_router
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Autonomous Browser Agent", lifespan=lifespan)
app.include_router(tasks_router)


@app.get("/health")
async def health():
    return {"status": "ok"}