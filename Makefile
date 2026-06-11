# Convenience targets for local (no-Docker) development.
# Assumes a Postgres reachable at the DATABASE_URL in backend/.env
# (or `make db` to start one via docker compose).

BACKEND := backend
VENV := $(BACKEND)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help
help:
	@echo "Targets:"
	@echo "  make install      Create venv + install backend deps, install frontend deps"
	@echo "  make db           Start Postgres via docker compose"
	@echo "  make seed         Seed the 5 lender policies"
	@echo "  make backend      Run the FastAPI dev server (:8000)"
	@echo "  make frontend     Run the Vite dev server (:5173)"
	@echo "  make test         Run the backend test-suite (SQLite, no infra)"

.PHONY: install
install:
	python3 -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -r $(BACKEND)/requirements.txt
	cd frontend && npm install

.PHONY: db
db:
	docker compose up -d db

.PHONY: seed
seed:
	cd $(BACKEND) && .venv/bin/python -m app.seed.seed_lenders

.PHONY: backend
backend:
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: frontend
frontend:
	cd frontend && npm run dev

.PHONY: test
test:
	cd $(BACKEND) && DATABASE_URL=sqlite:///./test.db .venv/bin/python -m pytest -q
