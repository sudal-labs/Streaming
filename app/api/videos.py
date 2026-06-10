import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.params import Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.schemas import (
    VideoUploadResponse,
    VideoStatusResponse,
    VideoListItem,
    VideoListResponse, VideoStreamResponse,
)
from app.db.models import Video, VideoStatus, get_db
from app.services.kafka import publish_transcode_event
from app.services.storage import upload_fileobj, get_presigned_url

router = APIRouter(
    prefix="/videos",
    tags=["videos"]
)

def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"허용되지 않는 파일 형식입니다. 허용: {settings.allowed_extensions}",
        )
    return ext

@router.post("", status_code=202, response_model=VideoUploadResponse)
async def upload_video(
        file: UploadFile = File(...),
        title: str = Form(...),
        description: str = Form(None),
        db: AsyncSession = Depends(get_db),
):
    """
    영상 업로드
    1. MinIO에 원본 저장
    2. DB 저장
    3. Kafka에 트랜스코딩 이벤트 발행
    4. 202 즉시 반환
    """
    _validate_extension(file.filename or "")

    video_id = str(uuid.uuid4())
    ext = Path(file.filename or "video").suffix
    object_key = f"originals/{video_id}{ext}"

    # 파일 읽기 (크기 검증 포함)
    chunks = []
    file_size = 0
    while chunk := await file.read(1024 * 1024):
        file_size += len(chunk)
        if file_size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"파일 크기가 {settings.MAX_FILE_SIZE_MB}MB를 초과합니다.",
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    # -- 1. MinIO 업로드 (블로킹 작업 -> executor로 비동기 처리)
    await asyncio.get_event_loop().run_in_executor(
        None, upload_fileobj, object_key, data, "video/mp4"
    )

    # -- 2. DB 저장
    video = Video(
        id=video_id,
        title=title,
        description=description,
        original_object_key=object_key,
        file_size=file_size,
        status=VideoStatus.PENDING,
    )
    db.add(video)
    await db.commit()

    # -- 3. Kafka 이벤트 발행
    await publish_transcode_event(video_id, object_key)

    return VideoUploadResponse(video_id=video_id, status=VideoStatus.PENDING, title=title)


@router.get("/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(
        video_id: str,
        db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Video)
        .where(Video.id == video_id)
    )
    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=400,
            detail="영상을 찾을 수 없습니다."
        )

    return VideoStatusResponse(
        video_id=video_id,
        status=video.status,
        duration=video.duration,
        error=video.error_message,
    )


@router.get("/{video_id}/stream", response_model=VideoStreamResponse)
async def stream_video(
        video_id: str,
        db: AsyncSession = Depends(get_db)
):
    """
    HLS 플레이리스트 Presigned URL 반환
    클라이언트가 MinIO에 직접 접근 → API 서버 부하 없음
    """
    result = await db.execute(
        select(Video)
        .where(Video.id == video_id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다.")
    if video.status != VideoStatus.DONE:
        raise HTTPException(status_code=400, detail=f"아직 스트리밍 불가 상태입니다. 현재: {video.status}")

    playlist_key = f"{video.hls_object_prefix}/playlist.m3u8"
    presigned_url = await asyncio.get_event_loop().run_in_executor(
        None,
        get_presigned_url,
        playlist_key,
        3600
    )

    return VideoStreamResponse(
        video_id=video_id,
        playlist_url=presigned_url,
    )


@router.get("", response_model=VideoListResponse)
async def list_videos(
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """영상 목록 조회 (페이지네이션)"""
    offset = (page - 1) * size

    total_result = await db.execute(
        select(func.count())
        .select_from(Video)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Video)
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    videos = result.scalars().all()

    items = [
        VideoListItem(
            video_id=v.id,
            title=v.title,
            status=v.status,
            duration=v.duration,
            created_at=v.created_at,
        )
        for v in videos
    ]

    return VideoListResponse(
        total=total,
        items=items
    )