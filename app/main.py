import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.videos import router as video_router
from app.db.models import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(
    title="Video Streaming Service",
    description="영상 업로드 → HLS 트랜스코딩 → 스트리밍 (1단계 MVP)",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(video_router)


@app.get("/health")
async def health():
    return {"status": "ok"}