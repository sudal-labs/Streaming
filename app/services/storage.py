import io

from minio import Minio

from app.config import settings

_client: Minio

def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client

"""버킷이 없으면 생성"""
def ensure_bucket():
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)

"""바이트 데이터를 MinIO에 업로드"""
def upload_fileobj(
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
):
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )

"""로컬 파일을 MinIO에 업로드"""
def upload_file(
        object_key: str,
        file_path: str,
        content_type: str = "application/octet-stream",
):
    client = get_minio_client()
    client.fput_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        file_path=file_path,
        content_type=content_type,
    )

"""MinIO에서 로컬로 다운로드"""
def download_file(
        object_key: str,
        dest_path: str
):
    client = get_minio_client()
    client.fget_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        file_path=dest_path,
    )

"""Presigned URL 발급"""
def get_presigned_url(
        object_key: str,
        expires_seconds: int = 3600
) -> str:
    from datetime import timedelta
    client = get_minio_client()
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_key,
        expires=timedelta(seconds=expires_seconds),
    )

"""prefix로 시작하는 오브젝트 키 목록 반환"""
def list_objects(prefix: str) -> list[str]:
    client = get_minio_client()
    objects = client.list_objects(settings.MINIO_BUCKET, prefix=prefix)

    return [obj.object_name for obj in objects]