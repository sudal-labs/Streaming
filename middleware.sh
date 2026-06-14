#!/bin/bash

COMPOSE_FILE="$(pwd)/podman/podman-compose.yml"

case "$1" in
  up)
    echo "▶ 미들웨어 시작..."
    podman compose -f "$COMPOSE_FILE" up -d
    echo ""
    echo "MinIO 콘솔  → http://localhost:9001  (minioadmin / minioadmin)"
    echo "Kafka      → localhost:9092"
#    echo "Redis      → localhost:6379"
#    echo "Prometheus → http://localhost:9090"
#    echo "Grafana    → http://localhost:3000  (admin / admin)"
    ;;
  down)
    echo "▶ 미들웨어 종료..."
    podman compose -f "$COMPOSE_FILE" down
    ;;
  restart)
    podman compose -f "$COMPOSE_FILE" down
    podman compose -f "$COMPOSE_FILE" up -d
    ;;
  clean)
    echo "⚠️  볼륨 포함 전체 삭제"
    read -p "계속할까요? (y/N) " confirm
    if [ "$confirm" = "y" ]; then
      podman compose -f "$COMPOSE_FILE" down -v
    fi
    ;;
  logs)
    podman compose -f "$COMPOSE_FILE" logs -f ${2:-""}
    ;;
  status)
    podman compose -f "$COMPOSE_FILE" ps
    ;;
  *)
    echo "사용법: ./middleware.sh [up|down|restart|clean|logs|status]"
    ;;
esac