from pathlib import Path

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./video_streaming.db"
    UPLOAD_DIR: str = "storage/uploads"
    HLS_DIR: str = "storage/hls"
    MAX_FILE_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: str = "mp4,mov,avi,mkv"

    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"

    @property
    def allowed_extensions(self) -> list[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    model_config = {"env_file": ".env"}

settings = Settings()

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.HLS_DIR).mkdir(parents=True, exist_ok=True)