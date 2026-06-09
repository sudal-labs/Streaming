import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.db.models import Video, VideoStatus, AsyncSessionLocal

logger = logging.getLogger(__name__)


async def _get_duration(input_path: str) -> int | None:
    """ffprobe로 영상 길이(초) 추출"""
    try:
        proc = await asyncio.create_subprocess_exec(
            settings.FFPROBE_PATH, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        return int(float(stdout.decode().strip()))
    except Exception as e:
        return None

async def _update_status(
        video_id: str,
        status: VideoStatus,
        hls_path: str | None = None,
        duration: int | None = None,
        error_message: str | None = None,
):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video)
            .where(Video.id == video_id)
        )
        video = result.scalar_one_or_none()
        if not video:
            return
        video.status = status

        if hls_path:
            video.hls_path = hls_path
        if duration:
            video.duration = duration
        if error_message:
            video.error_message = error_message
        await db.commit()

async def transcode_to_hls(video_id: str, input_path: str):
    """
    FFmpeg으로 MP4 → HLS 변환
    출력: storage/hls/{video_id}/playlist.m3u8 + segment_*.ts
    """
    output_dir = Path(settings.HLS_DIR) / video_id
    output_dir.mkdir(parents=True, exist_ok=True)
    playlist_path = output_dir / "playlist.m3u8"

    await _update_status(video_id, VideoStatus.PROCESSING)
    logger.info(f"[{video_id}] 트랜스코딩 시작: {input_path}")

    try:
        duration = await _get_duration(input_path)

        # FFmpeg: MP4 → HLS (720p 단일 화질, 세그먼트 6초)
        cmd = [
            settings.FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-vf", "scale=-2:720",          # 720p, 가로는 짝수 자동 계산
            "-b:v", "2500k",                # 비디오 비트레이트
            "-b:a", "128k",                 # 오디오 비트레이트
            "-hls_time", "6",               # 세그먼트 길이 (초)
            "-hls_playlist_type", "vod",    # VOD 타입 (전체 세그먼트 목록 포함)
            "-hls_segment_filename", str(output_dir / "segment_%03d.ts"),
            str(playlist_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            error = stderr.decode()[-500:]
            logger.error(f"[{video_id}] FFmpeg 실패: {error}")
            await _update_status(video_id, VideoStatus.FAILED, error_message=error)
            return

        logger.info(f"[{video_id}] 트랜스코딩 완료")
        await _update_status(
            video_id,
            VideoStatus.DONE,
            hls_path=str(playlist_path),
            duration=duration,
        )

    except Exception as e:
        logger.exception(f"[{video_id}] 예외 발생")
        await _update_status(video_id, VideoStatus.FAILED, error_message=str(e))
