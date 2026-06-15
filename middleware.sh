#!/bin/bash

COMPOSE_FILE="$(pwd)/podman/compose.yml"

case "$1" in
  up)
    echo "▶ 전체 서비스 시작 (빌드 포함)..."
    podman compose -f "$COMPOSE_FILE" up -d
    echo ""
    echo "PostgreSQL → localhost:5432 (postgres / postgres)"
    echo "MinIO 콘솔  → http://localhost:9001  (minioadmin / minioadmin)"
    echo "Kafka      → localhost:9092"
#    echo "Redis      → localhost:6379"
#    echo "Prometheus → http://localhost:9090"
#    echo "Grafana    → http://localhost:3000  (admin / admin)"
    ;;

  down)
    echo "▶ 전체 서비스 종료..."
    podman compose -f "$COMPOSE_FILE" down
    ;;

  restart)
    podman compose -f "$COMPOSE_FILE" down
    podman compose -f "$COMPOSE_FILE" up -d --build
    ;;

  rebuild)
    SERVICE=${2:-"api worker"}
    echo "▶ $SERVICE 재빌드..."
    podman compose -f "$COMPOSE_FILE" up -d --build "$SERVICE"
    ;;

  clean)
    echo "⚠️  볼륨 포함 전체 삭제"
    read -p "계속할까요? (y/N) " confirm
    if [ "$confirm" = "y" ]; then
      podman compose -f "$COMPOSE_FILE" down -v
    fi
    ;;

  logs)
    SERVICE=${2:-""}
    podman compose -f "$COMPOSE_FILE" logs -f "$SERVICE"
    ;;

  status)
    podman compose -f "$COMPOSE_FILE" ps
    ;;

  *)
    echo "사용법: ./middleware.sh [명령어]"
    echo ""
    echo "명령어:"
    echo "  up              전체 서비스 시작 (이미지 빌드 포함)"
    echo "  down            전체 서비스 종료"
    echo "  restart         전체 재시작"
    echo "  rebuild [서비스] 코드 변경 후 재빌드 (기본: api worker)"
    echo "  clean           볼륨 포함 전체 삭제"
    echo "  logs [서비스]    로그 확인"
    echo "  status          실행 상태 확인"
    ;;
esac