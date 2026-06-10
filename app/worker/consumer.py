import asyncio
import json
import logging
import tempfile
from pathlib import Path

from aiofiles import stderr
from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from app.config import settings
from app.db.models import VideoStatus, AsyncSessionLocal, Video
from app.services.storage import download_file, upload_file

logger = logging.getLogger(__name__)

async def _get_duration(input_path: str) -> int | None:
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
        hls_object_prefix: str | None = None,
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

        if hls_object_prefix:
            video.hls_object_prefix = hls_object_prefix
        if duration:
            video.duration = duration
        if error_message:
            video.error_message = error_message

        await db.commit()

async def _transcode(
        video_id: str,
        object_key: str
):
    """
    1. MinIO에서 원본 다운로드
    2. FFmpeg으로 HLS 변환
    3. HLS 세그먼트 MinIO에 업로드
    4. 임시 파일 정리
    """
    logger.info(f"[{video_id}] 트랜스코딩 시작")
    await _update_status(video_id, VideoStatus.PROCESSING)

    # 임시 디렉토리에서 작업 (완료 후 삭제)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = str(tmp_path / "input.mp4")
        output_dir = tmp_path / "hls"
        output_dir.mkdir()
        playlist_path = str(output_dir / "playlist.m3u8")

        try:
            # -- 1. 원본 다운로드
            logger.info(f"[{video_id}] MinIO ekdnsfhem: {object_key}")
            await asyncio.get_event_loop().run_in_executor(
                None,
                download_file,
                object_key,
                input_path
            )

            # -- 2. 영상 길이 추출
            duration = await _get_duration(playlist_path)

            # -- 3. FFmpeg 트랜스코딩
            cmd = [
                settings.FFMPEG_PATH, "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-vf", "scale=-2:720",
                "-b:v", "2500k",
                "-b:a", "128k",
                "-hls_time", "6",
                "-hls_playlist_type", "vod",
                "-hls_segment_filename", str(output_dir / "segment_%03d.ts"),
                playlist_path,
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

            # -- 4. HLS 파일 MinIO 업로드
            hls_prefix = f"hls/{video_id}"
            for hls_file in output_dir.iterdir():
                object_name = f"{hls_prefix}/{hls_file.name}"
                content_type = "application/x-mpegURL" if hls_file.suffix == ".m3u8" else "video/mp2t"

                await asyncio.get_event_loop().run_in_executor(
                    None,
                    upload_file,
                    object_name,
                    str(hls_file),
                    content_type
                )
            logger.info(f"[{video_id}] MinIO 업로드 완료: {hls_prefix}")

            await _update_status(
                video_id,
                VideoStatus.DONE,
                hls_object_prefix=hls_prefix,
                duration=duration,
            )
            logger.info(f"[{video_id}] 트랜스코딩 완료")

        except Exception as e:
            logger.exception(f"[{video_id}] 예외 발생")

            await _update_status(video_id, VideoStatus.FAILED, error_message=str(e))

async def consume():
    consumer = AIOKafkaConsumer(
        settings.KAFKA_TOPIC_TRANSCODE,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_GROUP_ID,
        value_deserializer=lambda v: json.loads(v.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    await consumer.start()
    logger.info("Worker 시작. 메시지 대기 중...")

    try:
        async for message in consumer:
            video_id = message.value.get("video_id")
            object_key = message.value.get("object_key")

            if not video_id or not object_key:
                logger.warn(f"잘못된 메시지: {message.value}")
                await consumer.commit()
                continue

            await _transcode(video_id, object_key)
            await consumer.commit()

    finally:
        await consumer.stop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    asyncio.run(consume())