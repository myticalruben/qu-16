# ============================================================================
# qu16-control — tareas habituales de desarrollo y despliegue
# ============================================================================
# Requisitos: Python 3.12+, Node 22+ y (para los objetivos Docker) Compose v2.
# Ejecuta `make help` para ver la lista de objetivos.
# ============================================================================

BACKEND_DIR    ?= backend
FRONTEND_DIR   ?= frontend
VENV           ?= $(BACKEND_DIR)/.venv
PYTHON         ?= $(VENV)/bin/python
PIP            ?= $(VENV)/bin/pip
COMPOSE        ?= docker compose
BACKEND_PORT   ?= 8000
FRONTEND_PORT  ?= 5173

# IP/puerto de la mesa que usará `make dev` (los contenedores usan los valores
# por defecto del docker-compose.yml o un archivo .env).
QU16_MIXER_HOST ?= 192.168.100.67
QU16_MIXER_PORT ?= 51326

.DEFAULT_GOAL := help
.PHONY: help install test dev build up down logs clean

help: ## Muestra esta ayuda
	@echo "qu16-control — objetivos disponibles:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables: BACKEND_DIR=$(BACKEND_DIR) FRONTEND_DIR=$(FRONTEND_DIR)"

install: ## Crea el venv del backend e instala dependencias de ambos lados
	@echo "==> Backend: venv + instalación editable con extras de desarrollo"
	cd $(BACKEND_DIR) && python3 -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -e ".[dev]"
	@echo "==> Frontend: dependencias npm"
	cd $(FRONTEND_DIR) && if [ -f package-lock.json ]; then npm ci --include=dev; else npm install --include=dev; fi

test: ## Ejecuta pytest (backend) y vitest (frontend)
	@echo "==> pytest"
	cd $(BACKEND_DIR) && .venv/bin/python -m pytest -q
	@echo "==> vitest"
	cd $(FRONTEND_DIR) && npx vitest run

dev: ## Arranca backend (8000) y frontend (5173) en paralelo
	@echo "Backend  -> http://localhost:$(BACKEND_PORT)  (docs en /docs)"
	@echo "Frontend -> http://localhost:$(FRONTEND_PORT)"
	@echo "Ctrl+C detiene ambos procesos."
	@trap 'kill $$(jobs -p) 2>/dev/null; exit 130' INT TERM; \
	( cd $(BACKEND_DIR) && QU16_MIXER_HOST=$(QU16_MIXER_HOST) QU16_MIXER_PORT=$(QU16_MIXER_PORT) \
		PYTHONPATH=src .venv/bin/python -m uvicorn qu16_api.main:app --reload --host 0.0.0.0 --port $(BACKEND_PORT) ) & \
	( cd $(FRONTEND_DIR) && npm run dev ) & \
	wait

build: ## Construye las imágenes Docker de backend y frontend
	$(COMPOSE) build

up: ## Crea/levanta los contenedores en segundo plano (reconstruye imágenes)
	$(COMPOSE) up -d --build

down: ## Detiene y elimina los contenedores (conserva las imágenes)
	$(COMPOSE) down

logs: ## Sigue los logs de los servicios
	$(COMPOSE) logs -f --tail=100

clean: ## Borra venv, node_modules, dist y cachés generadas
	rm -rf $(VENV) $(FRONTEND_DIR)/node_modules $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/coverage
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache -o -name .vite -o -name '*.egg-info' \) -prune -exec rm -rf {} +
