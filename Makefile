.PHONY: help up up-d down down-clean logs ps health \
        backend-shell backend-test backend-lint backend-format backend-alembic \
        frontend-shell frontend-typecheck \
        docs-lint docs-fix \
        sync lock

ARGS ?=

help:  ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up:  ## docker compose up (foreground, all services)
	docker compose up

up-d:  ## docker compose up -d (detached)
	docker compose up -d

down:  ## docker compose down (keep volumes)
	docker compose down

down-clean:  ## docker compose down -v (drops postgres volume — destructive)
	@echo ">>> WARNING: this will drop the postgres volume. Press Ctrl-C within 3s to abort."
	@sleep 3
	docker compose down -v

logs:  ## docker compose logs -f
	docker compose logs -f

ps:  ## docker compose ps
	docker compose ps

health:  ## curl localhost:8000/health (smoke check)
	curl -fsS --max-time 5 -i http://localhost:8000/health

# ---- Backend ----
backend-shell:  ## bash inside the backend container
	docker compose exec backend bash

backend-test:  ## pytest inside the backend container
	docker compose exec backend pytest

backend-lint:  ## ruff check + black --check inside the backend container
	docker compose exec backend ruff check .
	docker compose exec backend black --check .

backend-format:  ## ruff check --fix + black inside the backend container
	docker compose exec backend ruff check --fix .
	docker compose exec backend black .

backend-alembic:  ## alembic <args> inside the backend container (ARGS="current" or "upgrade head")
	docker compose exec backend alembic $(ARGS)

# ---- Frontend ----
frontend-shell:  ## sh inside the frontend container
	docker compose exec frontend sh

frontend-typecheck:  ## tsc --noEmit inside the frontend container
	docker compose exec frontend npm run typecheck

# ---- Docs ----
DOCS_GLOBS := "**/*.md" "!.claude/**" "!frontend/node_modules/**" "!backend/.venv/**" "!design/**" "!node_modules/**"

docs-lint:  ## markdownlint all project .md files
	markdownlint-cli2 --config .markdownlint.json $(DOCS_GLOBS)

docs-fix:  ## markdownlint --fix all project .md files (auto-corrects fixable issues)
	markdownlint-cli2 --fix --config .markdownlint.json $(DOCS_GLOBS)

# ---- Local Python env (for IDE autocomplete and ad-hoc scripts) ----
sync:  ## uv sync — create/refresh ./backend/.venv from uv.lock
	cd backend && uv sync --extra dev

lock:  ## uv lock — refresh backend/uv.lock from pyproject.toml
	cd backend && uv lock
