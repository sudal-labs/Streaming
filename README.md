# Video Streaming Service — 2단계

영상 업로드 → Kafka → Worker 트랜스코딩 → MinIO HLS 스트리밍

## 구조

```
app/
├── main.py               # FastAPI 앱
├── config.py             # 환경변수
├── api/videos.py         # API 엔드포인트
├── core/schemas.py       # Pydantic 스키마
├── db/models.py          # SQLAlchemy 모델
├── services/
│   ├── storage.py        # MinIO 클라이언트
│   └── kafka.py          # Kafka Producer
└── worker/
    └── consumer.py       # Kafka Consumer + FFmpeg
podman/
└── compose.yml           # Kafka + MinIO
```

## 흐름

```
POST /videos
  → MinIO에 원본 저장 (originals/{video_id}.mp4)
  → DB 저장 (status: PENDING)
  → Kafka 이벤트 발행 (video.transcode 토픽)
  → 202 즉시 반환

Worker (별도 프로세스)
  → Kafka 메시지 소비
  → MinIO에서 원본 다운로드
  → FFmpeg 트랜스코딩 (720p HLS)
  → HLS 세그먼트 MinIO 업로드 (hls/{video_id}/)
  → DB status → DONE
  → Kafka 오프셋 커밋

GET /videos/{id}/stream
  → MinIO Presigned URL 반환 (1시간 유효)
  → 클라이언트가 MinIO에 직접 접근
```

## 실행 방법

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env에서 FFMPEG_PATH 로컬 경로로 수정 (Mac: /opt/homebrew/bin/ffmpeg)

# 2. 패키지 설치
pip install -r requirements.txt

# 3. FFmpeg 설치
brew install ffmpeg  # macOS
# sudo apt install ffmpeg  # Ubuntu

# 4. 미들웨어 실행 (Kafka + MinIO)
chmod +x middleware.sh
./middleware.sh up

# 5. API 서버 실행
uvicorn app.main:app --reload

# 6. Worker 실행 (별도 터미널)
python -m app.worker.consumer
```

## 미들웨어 명령어

```bash
./middleware.sh up               # 시작
./middleware.sh down             # 종료
./middleware.sh restart          # 재시작
./middleware.sh status           # 상태 확인
./middleware.sh logs             # 전체 로그
./middleware.sh logs kafka       # Kafka 로그만
./middleware.sh logs minio       # MinIO 로그만
./middleware.sh clean            # 볼륨 포함 전체 삭제 (데이터 초기화)
```

## MinIO 콘솔

http://localhost:9001 (minioadmin / minioadmin)

## 1단계 vs 2단계 비교

| | 1단계 | 2단계 |
|---|---|---|
| 파일 저장 | 로컬 디스크 | MinIO |
| 트랜스코딩 | BackgroundTasks | Kafka + Worker |
| 서버 재시작 시 | 작업 유실 | Kafka 메시지 보존 |
| Worker 확장 | 불가 | 독립 수평 확장 |
| 스트리밍 서빙 | API 서버 직접 | MinIO Presigned URL |
