import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.videos import router as video_router
from app.db.models import init_db
from app.services.kafka import stop_producer
from app.services.storage import ensure_bucket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    ensure_bucket()
    yield
    await stop_producer()

app = FastAPI(
    title="Video Streaming Service",
    description="영상 업로드 -> Kafka -> Worker 트랜스코딩 -> MinIO HLS 스트리밍 (2단계)",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(video_router)


@app.get("/health")
async def health():
    return {"status": "ok"}