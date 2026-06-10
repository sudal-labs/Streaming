from datetime import datetime

from pydantic import BaseModel

from app.db.models import VideoStatus


class VideoUploadResponse(BaseModel):
    video_id: str
    status: VideoStatus
    title: str

class VideoStatusResponse(BaseModel):
    video_id: str
    status: VideoStatus
    duration: int | None = None
    error: str | None = None

class VideoStreamResponse(BaseModel):
    video_id: str
    playlist_url: str # presigned URL

class VideoListItem(BaseModel):
    video_id: str
    title: str
    status: VideoStatus
    duration: int | None
    created_at: datetime

    model_config = {"from_attributes": True}

class VideoListResponse(BaseModel):
    total: int
    items: list[VideoListItem]