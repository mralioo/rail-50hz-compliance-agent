# Rail50Hz.ai — dev workflow shortcuts
VENV := backend/.venv
PY := $(VENV)/bin/python

.PHONY: setup backend sample test frontend docker viewer

setup: ## create venv + install backend deps
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r backend/requirements.txt

PORT ?= 8000

backend: ## run the FastAPI gateway (override port: make backend PORT=8001)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port $(PORT)

sample: ## generate the demo DXF with injected violations
	cd backend && .venv/bin/python scripts/make_sample_dxf.py

test: ## run backend tests
	cd backend && .venv/bin/python -m pytest tests/ -v

frontend: ## run the Flutter desktop app (Linux)
	cd frontend && flutter run -d linux

docker: ## build the Cloud Run image
	docker build -f deployment/Dockerfile -t rail50hz-backend .

viewer: ## check deps, start backend if needed, open the interactive cad-viewer
	backend/scripts/launch_viewer.sh
