#! /bin/bash

set -o

COMPOSE_FILE="$(dirname "$0")/podman/podman-compose.yml"

case "$1" in
  up)
    echo "▶ 미들웨어 시작..."
    podman compose -f "$COMPOSE_FILE" up -d
    echo ""
    echo "✅ 완료! 서비스 상태:"
    podman compose -f "$COMPOSE_FILE" ps
    echo ""
    echo "MinIO 콘솔 → http://localhost:9001  (minioadmin / minioadmin)"
    echo "Kafka      → localhost:9092"
    ;;

  down)
    echo "▶ 미들웨어 종료..."
    podman compose -f "$COMPOSE_FILE" down
    echo "✅ 종료 완료"
    ;;

  restart)
    echo "▶ 미들웨어 재시작..."
    podman compose -f "$COMPOSE_FILE" down
    podman compose -f "$COMPOSE_FILE" up -d
    echo "✅ 재시작 완료"
    ;;

  clean)
    echo "⚠️  볼륨 포함 전체 삭제 (데이터 초기화)"
    read -p "계속할까요? (y/N) " confirm
    if [ "$confirm" = "y" ]; then
      podman compose -f "$COMPOSE_FILE" down -v
      echo "✅ 삭제 완료"
    else
      echo "취소됨"
    fi
    ;;

  logs)
    SERVICE=${2:-""}
    podman compose -f "$COMPOSE_FILE" logs -f $SERVICE
    ;;

  status)
    podman compose -f "$COMPOSE_FILE" ps
    ;;

  *)
    echo "사용법: ./middleware.sh [명령어]"
    echo ""
    echo "명령어:"
    echo "  up       미들웨어 시작 (백그라운드)"
    echo "  down     미들웨어 종료"
    echo "  restart  재시작"
    echo "  clean    볼륨 포함 전체 삭제 (데이터 초기화)"
    echo "  logs     전체 로그 (./middleware.sh logs kafka 처럼 서비스 지정 가능)"
    echo "  status   실행 상태 확인"
    ;;
esac