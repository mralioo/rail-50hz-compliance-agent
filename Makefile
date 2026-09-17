# Rail50Hz.ai — dev workflow shortcuts
VENV := backend/.venv
PY := $(VENV)/bin/python

.PHONY: setup backend sample test frontend docker viewer kb-up kb-down kb-reset kb-ingest kb-compare docling-extract docling-refine kb-ingest-project visualize-embeddings reindex-refined webapp-install webapp run craftsman-check

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

kb-up: ## start OpenSearch + Neo4j (local KB evaluation stack, see docs/OPENSEARCH_NEO4J_EVALUATION.md)
	docker compose --env-file backend/.env -f docker-compose.kb.yml up -d

kb-down: ## stop the KB evaluation stack (data persists)
	docker compose --env-file backend/.env -f docker-compose.kb.yml down

kb-reset: ## stop and wipe all KB evaluation data
	docker compose --env-file backend/.env -f docker-compose.kb.yml down -v

kb-ingest: ## ingest the regulation corpus into both OpenSearch and Neo4j
	cd backend && .venv/bin/python scripts/kb_ingest_opensearch.py
	cd backend && .venv/bin/python scripts/kb_ingest_neo4j.py

kb-compare: ## run the hybrid fusion PoC (override: make kb-compare QUERY="...")
	cd backend && .venv/bin/python scripts/kb_compare.py "$(QUERY)"

PROJECT ?= project_1

docling-extract: ## extract dataset/raw/<project> into clean Markdown + images via the Docling server (override: make docling-extract PROJECT=... / add FLAGS="--force --limit 5 --force-ocr")
	cd backend && .venv/bin/python scripts/docling_ingest.py --project $(PROJECT) $(FLAGS)

docling-refine: ## LLM-clean dataset/clean/<project> into dataset/super_clean/<project> (run docling-extract first; override FLAGS="--force --limit 5 --concurrency 4")
	cd backend && .venv/bin/python scripts/docling_refine.py --project $(PROJECT) $(FLAGS)

SOURCE ?= clean

kb-ingest-project: ## ingest a project's Markdown corpus into OpenSearch + Neo4j (run docling-extract first; override SOURCE=super_clean after docling-refine)
	cd backend && .venv/bin/python scripts/project_kb_ingest_opensearch.py --project $(PROJECT) --source $(SOURCE)
	cd backend && .venv/bin/python scripts/project_kb_ingest_neo4j.py --project $(PROJECT) --source $(SOURCE)

ATLAS_PORT ?= 5055

visualize-embeddings: ## export a project's indexed vectors + images + launch the Embedding Atlas viewer (run kb-ingest-project first)
	cd backend && .venv/bin/python scripts/project_kb_export_atlas.py --project $(PROJECT)
	-fuser -k $(ATLAS_PORT)/tcp 2>/dev/null
	cd backend && .venv/bin/embedding-atlas workdir/atlas/$(PROJECT).parquet --port $(ATLAS_PORT) \
		--text text --vector embedding --image image \
		--table images workdir/atlas/$(PROJECT)_images.parquet \
		--table-relation images 'mainKey=chunk_id;key=chunk_id'

reindex-refined: ## after docling-refine: re-embed the LLM-cleaned+described corpus into OpenSearch, re-export, relaunch Atlas
	$(MAKE) kb-ingest-project PROJECT=$(PROJECT) SOURCE=super_clean
	$(MAKE) visualize-embeddings PROJECT=$(PROJECT)

webapp-install: ## install the React web shell's dependencies (OmniDraft · GLEIS OS)
	cd webapp && npm install

webapp: ## run the React web shell (Vite dev server, see docs/WEBAPP.md)
	cd webapp && npm run dev

run: ## start the backend (if not already up) + the dashboard, one command, Ctrl+C stops both
	scripts/run.sh

craftsman-check: ## verify the Craftsman agent's FreeCAD engine resolves (no server needed - see docs/CRAFTSMAN_AGENT.md)
	cd backend && .venv/bin/python -c "\
	from app.craftsman.freecad_bridge import find_freecadcmd, find_worker; \
	cmd, worker = find_freecadcmd(), find_worker(); \
	print(f'FreeCADCmd: {cmd or \"NOT FOUND — set FREECADCMD_PATH in backend/.env\"}'); \
	print(f'worker.py:  {worker or \"NOT FOUND\"}')"
