
COMPOSE = podman compose -f podman/compose.yml

.PHONY: setup run down logs status rebuild

# 이미지 빌드
setup:
	@podman info >/dev/null 2>&1 || { \
		echo "Podman Machine이 실행되고 있지 않습니다."; \
		echo "Podman Machine을 실행한 뒤 다시 시도해주세요."; \
		exit 1; \
	}
	$(COMPOSE) build

# 전체 서비스 실행
run:
	@podman info >/dev/null 2>&1 || { \
		echo "Podman Machine이 실행되고 있지 않습니다."; \
		echo "Podman Machine을 실행한 뒤 다시 시도해주세요."; \
		exit 1; \
	}
	$(COMPOSE) up -d
	@echo ""
	@echo "API        → http://localhost:8000/docs"
	@echo "PostgreSQL → localhost:5432  (postgres / postgres)"
	@echo "MinIO 콘솔  → http://localhost:9001  (minioadmin / minioadmin)"
	@echo "Kafka      → localhost:9092"

# 컨테이너, 볼륨, 로컬 빌드 이미지 정리
down:
	@read -p "볼륨과 로컬 이미지를 모두 삭제합니다. 계속할까요? (y/N) " confirm && \
	[ "$$confirm" = "y" ] && $(COMPOSE) down -v --rmi local || echo "취소됐습니다."

# 로그 확인 (ex: make logs api)
logs:
	$(COMPOSE) logs -f $(filter-out $@,$(MAKECMDGOALS))

# 실행 상태 확인
status:
	$(COMPOSE) ps

# 코드 변경 후 특정 서비스만 재빌드 (ex: make rebuild api worker)
rebuild:
	$(COMPOSE) up -d --build $(filter-out $@,$(MAKECMDGOALS))

# 오류 방지
%:
 @: