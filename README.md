# Video Streaming Service — 1단계 MVP

영상 업로드 → FFmpeg 트랜스코딩 → HLS 스트리밍 파이프라인

## 구조

```
video-streaming/
├── app/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── config.py            # 환경변수 설정
│   ├── api/
│   │   └── videos.py        # API 라우터 (5개 엔드포인트)
│   ├── core/
│   │   └── schemas.py       # Pydantic 스키마
│   ├── db/
│   │   └── models.py        # SQLAlchemy 모델 + 세션
│   └── services/
│       └── transcoding.py   # FFmpeg 트랜스코딩 서비스
├── storage/
│   ├── uploads/             # 업로드된 원본 파일
│   └── hls/                 # 변환된 HLS 파일
├── .env
└── requirements.txt
```

## 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. FFmpeg 설치 (필수)
# macOS: brew install ffmpeg
# Ubuntu: sudo apt install ffmpeg

# 3. 서버 실행
uvicorn app.main:app --reload

# 4. API 문서 확인
open http://localhost:8000/docs
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /videos | 영상 업로드 (202 즉시 반환) |
| GET | /videos/{id}/status | 트랜스코딩 상태 조회 |
| GET | /videos/{id}/stream | HLS 플레이리스트(.m3u8) |
| GET | /videos/{id}/segments/{file} | HLS 세그먼트(.ts) |
| GET | /videos | 영상 목록 |

## 흐름

```
POST /videos
  → 파일 저장 (storage/uploads/)
  → DB 저장 (status: PENDING)
  → BackgroundTasks에 트랜스코딩 등록
  → 202 즉시 반환

백그라운드:
  → FFmpeg 실행 (MP4 → 720p HLS)
  → storage/hls/{video_id}/playlist.m3u8 생성
  → status: PROCESSING → DONE (or FAILED)

GET /videos/{id}/stream
  → playlist.m3u8 반환

클라이언트 (HLS.js 등):
  → segment_000.ts, segment_001.ts ... 순서대로 요청
```

## 환경변수 (.env)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| DATABASE_URL | sqlite+aiosqlite:///./video_streaming.db | DB 경로 |
| UPLOAD_DIR | storage/uploads | 원본 저장 경로 |
| HLS_DIR | storage/hls | HLS 출력 경로 |
| MAX_FILE_SIZE_MB | 500 | 최대 업로드 크기 |
| ALLOWED_EXTENSIONS | mp4,mov,avi,mkv | 허용 확장자 |

## 2단계 전환 시 변경점

| 현재 (1단계) | 2단계 |
|---|---|
| 로컬 디스크 저장 | MinIO (오브젝트 스토리지) |
| BackgroundTasks | Kafka + 별도 Worker |
| 단일 화질 (720p) | 다중 화질 (480p/720p/1080p) |
| SQLite | PostgreSQL |
