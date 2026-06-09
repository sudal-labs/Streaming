import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Request
from fastapi.params import Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.schemas import (
    VideoUploadResponse,
    VideoStatusResponse,
    VideoListItem,
    VideoListResponse,
)
from app.db.models import Video, VideoStatus, get_db
from app.services.transcoding import transcode_to_hls

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
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        title: str = Form(...),
        description: str = Form(None),
        db: AsyncSession = Depends(get_db),
):
    """영상 업로드 → 즉시 202 반환 → 백그라운드 트랜스코딩 시작"""
    _validate_extension(file.filename or "")

    video_id = str(uuid.uuid4())
    ext = Path(file.filename or "video").suffix
    save_path = Path(settings.UPLOAD_DIR) / f"{video_id}{ext}"

    # 파일 저장 (스트리밍으로 읽어 디스크에 기록)
    file_size = 0
    async with aiofiles.open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024): # 1MB 청크
            if file_size + len(chunk) > settings.max_file_size_bytes:
                save_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"파일 크기가 {settings.MAX_FILE_SIZE_MB}MB를 초과합니다.",
                )
            await f.write(chunk)
            file_size += len(chunk)

    # DB 저장
    video = Video(
        id=video_id,
        title=title,
        description=description,
        original_path=str(save_path),
        file_size=file_size,
        status=VideoStatus.PENDING,
    )
    db.add(video)
    await db.commit()

    # 백그라운드 트랜스코딩 등록
    background_tasks.add_task(transcode_to_hls, video_id, str(save_path))

    return VideoUploadResponse(video_id=video_id, status=VideoStatus.PENDING, title=title)

@router.get("/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(video_id: str, db: AsyncSession = Depends(get_db)):
    """트랜스코딩 진행 상태 조회"""
    result = await  db.execute(
        select(Video)
        .where(Video.id == video_id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(
            status_code=404,
            detail="영상을 찾을 수 없습니다."
        )

    return VideoStatusResponse(
        video_id=video_id,
        status=video.status,
        duration=video.duration,
        error=video.error_message,
    )

@router.get("/{video_id}/stream")
async def stream_video(video_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """HLS 플레이리스트(.m3u8) 반환"""
    result = await db.execute(
        select(Video)
        .where(Video.id == video_id)
    )
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="영상을 찾을 수 없습니다.")
    if video.status != VideoStatus.DONE:
        raise HTTPException(status_code=400, detail=f"아직 스트리밍 불가 상태입니다. 현재: {video.status}")

    playlist_path = Path(video.hls_path)
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="플레이리스트 파일이 없습니다.")

    base_url = f"{request.base_url}videos/{video_id}/segments"
    content = playlist_path.read_text()
    content = content.replace("segment_", f"{base_url}/segment_")

    return Response(
        content=content,
        media_type="application/x-mpegURL",
    )

@router.get("/{vide_id}/segments/{filename}")
async def serve_segment(video_id: str, filename: str):
    """HLS 세그먼트(.ts) 파일 서빙"""
    # 경로 순회 공격 방지
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")

    segment_path = Path(settings.HLS_DIR) / video_id / filename
    if not segment_path.exists():
        raise HTTPException(status_code=404, detail="세그먼트 파일이 없습니다.")

    return FileResponse(path=str(segment_path), media_type="video/mp2t")

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

    return VideoListResponse(total=total, items=items)