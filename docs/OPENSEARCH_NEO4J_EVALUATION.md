# OpenSearch (Vector) vs Neo4j (Graph) — Knowledge-Store Evaluation

Question: should the regulation knowledge base
(`backend/app/agent/rag.py`, currently naive keyword scoring over markdown
H2 sections) be replaced or augmented by a purpose-built **vector database**
(OpenSearch) and/or a **graph database** (Neo4j), and what is each uniquely
suited for in this domain? This doc is the hands-on evaluation harness and
decision record behind [`docs/design/ROADMAP_CHECKLIST.md`](design/ROADMAP_CHECKLIST.md)
item 5 ("Broaden the knowledge base").

## Verdict

**Use both, for different jobs — don't pick one.** OpenSearch is the right
default for "find the passage that answers this question" (semantic
retrieval, replaces `rag.py`'s keyword scoring). Neo4j is the right tool for
"is this citation still valid, and what replaced it" — a deterministic,
one-hop question a similarity search can only answer by luck. Neither
replaces Cognee's opportunistic chat-memory role outright, but both are
independently benchmarkable and browsable in a way Cognee's embedded
LanceDB/Kuzu are not, which is exactly what this evaluation needed. For the
next roadmap step: adopt OpenSearch as `rag.py`'s semantic-retrieval seam
first (bigger, more general win), and grow the Neo4j graph schema
incrementally as `Finding.regulation` gains structured citations — see §7.
(Verified 2026-07-30, on the real corpus, end-to-end, per below.)

## 1. What was tried

- `docker-compose.kb.yml` — local-only stack: `opensearch` 2.19.1 +
  `opensearch-dashboards` 2.19.1 (vector store + its built-in browser UI on
  port 5601), `neo4j:5.26-community` (graph store + its built-in Browser on
  port 7474). Started via `make kb-up`.
- New `backend/app/kb/` package: `corpus.py` (shared chunking, reused from
  `rag.py`'s existing folder-walk and H2-split — not reimplemented),
  `opensearch_store.py` (embed/index/query), `neo4j_store.py`
  (graph schema/ingest/query), `fusion.py` (hybrid merge).
- Ingested via `make kb-ingest` → `backend/scripts/kb_ingest_opensearch.py`
  + `kb_ingest_neo4j.py`, both reading the exact same
  `backend/data/regulations/{general,db}` folders `rag.list_knowledge_bases()`
  already exposes (today: `general` = 1 file, `db` = empty, `vde` planned).
- Queried via `make kb-compare QUERY="..."` → `backend/scripts/kb_compare.py`
  → `app.kb.fusion.compare()`.

This is an **evaluation harness that runs alongside the existing system** —
`rag.py`, `routes.py`, and every live endpoint are unmodified. Both new
stores are opt-in behind `OPENSEARCH_ENABLED`/`NEO4J_ENABLED` (default
`false`).

## 2. OpenSearch — semantic (vector) retrieval

### 2.1 Setup complexity (verified 2026-07-30)

- `opensearchproject/opensearch:2.19.1` image is **1.03 GB**;
  `opensearch-dashboards:2.19.1` adds another **432 MB**. Heaviest infra
  addition in this repo so far by a wide margin.
- **Real gotcha hit and fixed**: OpenSearch ≥2.12's security-plugin demo
  installer refuses to start ("Please define an environment variable
  'OPENSEARCH_INITIAL_ADMIN_PASSWORD'") even with
  `plugins.security.disabled=true` set — that flag only disables
  *enforcement* at runtime, not the startup-time password check. Fixed by
  also setting `OPENSEARCH_INITIAL_ADMIN_PASSWORD` in
  `docker-compose.kb.yml` (a throwaway local-dev value; the security plugin
  itself stays disabled so it's never actually used to authenticate).
- The `vm.max_map_count` gotcha commonly hit with OpenSearch/Elasticsearch
  on Linux was **not** encountered on this host (already sufficient) — worth
  rechecking on a fresh machine.
- Embedding provider: `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim)
  pulls in `torch` and CUDA wheels — multi-hundred-MB, several-minute
  install, by far the heaviest Python dependency in `requirements.txt`. The
  OpenAI provider (`text-embedding-3-small`, opt-in via
  `OPENSEARCH_EMBEDDING_PROVIDER=openai`) avoids this entirely since
  `openai` is already a dependency, at the cost of a per-call API charge and
  a network round trip.

### 2.2 Ingestion results on the real corpus

`make kb-ingest` → `kb_ingest_opensearch.py`, run against today's corpus
(`general`=1 file, `db`=0 files):

```
KB 'general' (General) — 1 file(s) on disk
KB 'db' (DB) — 0 file(s) on disk
Indexed 4 chunk(s) into 'rail50hz_regulations'
query probe -> 4 hit(s)
  top: [db_ril_954_9101.md] 'Machine-readable limits' (score=0.813)
```

4 chunks = the preamble + 3 H2 sections in `db_ril_954_9101.md`, matching
`app/kb/corpus.py::iter_chunks()`'s split exactly. Re-running the ingest
script a second time confirmed **idempotency** — index count stayed at 4
(deterministic `chunk_id` as the OpenSearch document `_id`, so re-indexing
upserts in place rather than duplicating).

### 2.3 Query relevance — verified sample queries

`minimum cable bending radius` → top hit: the `Machine-readable limits`
fenced block (score 0.813), i.e. the exact section containing
`min_cable_bending_radius_mm: 150`. On this tiny corpus every chunk is
somewhat relevant to a bending-radius query (it's a 4-section, 1-topic
document), so this is a weak signal of ranking quality specifically —
re-evaluate once the corpus is broader (§6).

### 2.4 Latency (verified 2026-07-30, via `kb_compare.py`'s printed timings)

- **First query in a fresh process: ~8.4–9.3s**, entirely dominated by
  lazily loading the `sentence-transformers` model
  (`Loading weights: 100%|██████████| 103/103`) — this happens once per
  process, not per query.
- The actual OpenSearch kNN search itself is fast (sub-second) once the
  model is warm; the CLI script's cold-start cost is a real, worth-noting
  finding for anyone benchmarking "OpenSearch latency" naively via repeated
  standalone script invocations — a long-lived process (e.g. the FastAPI
  backend itself) would pay this cost once at startup, not per request.

## 3. Neo4j — graph retrieval

### 3.1 Setup complexity (verified 2026-07-30)

- `neo4j:5.26-community` image is **356 MB** — a third the size of
  OpenSearch alone, and it started clean on the first `docker compose up`
  attempt (no equivalent to OpenSearch's admin-password gotcha).
  Healthcheck (`wget --spider http://localhost:7474`) passed within seconds.
- **Real bug hit and fixed during ingestion** (not a Docker/setup issue — a
  logic bug in `neo4j_store.py`): the initial `ingest()` only scanned the
  heading-less *preamble* chunk for the `active_codes:`/`deprecated_codes:`
  fenced block, but that block actually lives in the corpus's
  "Machine-readable limits" H2 section. Result: 0 `CITES` edges, only 2 of
  4 real codes present (the ones incidentally created by the
  `SUPERSEDED_BY` supersession-edge logic). Fixed by scanning every chunk
  of a document for `RULE_LINE_RE` matches instead of gating on
  `heading == ""` — `MERGE` makes this idempotent regardless of which
  chunk(s) match. Re-ingested and confirmed: **4 `Code` nodes** (`Ril
  954.9101`/`VDE 0100-520` active, `Ril 954.0107`/`Ril 813.0202`
  deprecated), **4 `CITES` edges**.
- One Cypher gotcha: the Python driver's `session.run(query, **kwargs)`
  signature already has a `query` parameter — passing a Cypher parameter
  also named `query` raises `TypeError: multiple values for argument
  'query'`. Renamed to `search_text` in `find_sections()`.

### 3.2 Schema

```
(:KnowledgeBase {id, name})
(:Document {id, name, kb_id})-[:IN_KB]->(:KnowledgeBase)
(:Document)-[:HAS_SECTION]->(:Section {id, heading, text})
(:Code {code, status: "active"|"deprecated"})
(:Document)-[:CITES]->(:Code)
(:Code)-[:SUPERSEDED_BY]->(:Code)
```

Grounded directly in the real corpus content
(`backend/data/regulations/db_ril_954_9101.md`):
- `active_codes`/`deprecated_codes` (the machine-readable fenced block) →
  `Code` nodes with `status`.
- The prose sentence in `## 4.5 Documentation` — "Ril 954.0107, superseded
  2021 by Ril 954.9101" — is regex-extracted (`app/kb/corpus.py::extract_supersessions`)
  into a real `(:Code {code:"Ril 954.0107"})-[:SUPERSEDED_BY]->(:Code {code:"Ril 954.9101"})`
  edge, not synthetic test data.

### 3.3 What graph-only queries can do that vector search cannot

- **`code_status("Ril 954.0107")`** walks the `SUPERSEDED_BY` chain and
  answers "is this code still valid, and if not, what replaced it?" — a
  question a vector or keyword index can only answer if the exact
  supersession sentence happens to be the top-scoring chunk for the query.
  The graph answers it deterministically regardless of chunk ranking.
- **`Finding.regulation` is a flat string today**
  (`backend/app/models/schemas.py`) — e.g. `"Ril 954.9101"` — with no
  structured link back to a specific clause/document/supersession chain.
  A future `(:Finding)-[:CITES]->(:Code)` edge (not built this iteration,
  intentionally forward-referenced in `neo4j_store.py`'s docstring) is
  exactly the relationship a graph DB can express and a vector index
  cannot: "show me every finding that currently cites a now-deprecated
  code" is a one-hop graph traversal, not a similarity search.

### 3.4 Latency (verified 2026-07-30, via `kb_compare.py`'s printed timings)

- Fulltext query (`db.index.fulltext.queryNodes`): **41–336 ms**.
- Graph `code_status()` lookup (per candidate code found in the hit text):
  **111–266 ms** for the whole batch in the test queries above.
- No cold-start penalty comparable to OpenSearch's embedding model load —
  the Neo4j driver connects fast and every query in this PoC was
  consistently sub-350ms end to end. On this corpus, **Neo4j is the faster
  of the two stores by roughly an order of magnitude**, though this
  compares "graph traversal + small fulltext index" against "load a
  384-dim transformer + kNN search," which is an apples-to-oranges
  comparison worth re-measuring with a warm OpenSearch process (e.g. inside
  a long-lived FastAPI worker) rather than a fresh CLI invocation each time.

## 4. Why not just use what Cognee already gives us for free

`backend/app/memory/cognee_store.py` already runs an *embedded* vector
store (LanceDB) and graph store (Kuzu) internally
(`docs/DATASET_INGESTION.md` §2.4), seeded from the same regulation corpus.
On paper this looks like it already covers both halves of this evaluation.
In practice it falls short of what this comparison needs:

| | Cognee (today) | OpenSearch / Neo4j (this PoC) |
| :--- | :--- | :--- |
| `kb_ids` filtering | No — global memory only, `recall()` takes no KB scope | Yes — both stores preserve the `general`/`db`/`vde` KB-id convention |
| Latency | ~15–25s per query (LLM-routed, per `docs/UX_AND_MEMORY.md`) | See §2.4/§3.4 above |
| Browsable UI | None | OpenSearch Dashboards (5601) + Neo4j Browser (7474), shipped free with the images |
| Graph schema control | Opaque — LLM decides what entities/edges to extract | Explicit, hand-designed schema grounded in the actual corpus fields (`active_codes`, supersession sentences) |
| Independently benchmarkable | No — vector and graph are fused into one `recall()` call | Yes — this is the entire point of the PoC |
| Cost/ops | Zero-deploy, but LLM-metered | Two more local Docker services, but free/local (default embedding provider) and inspectable |

Cognee remains the right choice for what it already does (fast to seed, zero
extra infra, good enough for opportunistic guideline recall in chat). It's
the wrong tool for *deliberately comparing* vector-vs-graph retrieval
quality and building an explicit, engineer-auditable regulation graph —
which is what this PoC is for.

## 5. Hybrid fusion PoC — verified end-to-end run

`make kb-compare QUERY="minimum cable bending radius"` (scoped to `--kb
general`) produced a merged, deduplicated, ranked list combining OpenSearch
semantic hits and Neo4j fulltext hits, with graph-sourced warnings attached
to any hit whose text cites a deprecated code:

```
- [db_ril_954_9101.md] Machine-readable limits: ```
min_cable_bending_radius_mm: 150
...
deprecated_codes: Ril 954.0107, Ril 813.0202
```
  [GRAPH WARNING] cites deprecated Ril 954.0107, superseded by Ril 954.9101

- [db_ril_954_9101.md] 4.2 Cable installation: Cables interfacing with...
- [db_ril_954_9101.md] (preamble): # DB Ril 954.9101 ...
- [db_ril_954_9101.md] 4.5 Documentation: Planning documents must cite
  active guidelines only. Citations of retired guidelines (e.g., Ril
  954.0107, superseded 2021 by Ril 954.9101) constitute template drift...
  [GRAPH WARNING] cites deprecated Ril 954.0107, superseded by Ril 954.9101

timings (ms): {'os_ms': 9295.8, 'neo4j_fulltext_ms': 41.4,
               'neo4j_status_ms': 111.3, 'total_ms': 9448.5}
```

A second run, `make kb-compare QUERY="Ril 954.0107"`, confirmed the same
`[GRAPH WARNING] ... superseded by Ril 954.9101` annotation appears —
**sourced from a live `SUPERSEDED_BY` graph traversal**, not string-matched
against the query. This is the concrete scenario the requirements asked
for: a semantic/fulltext hit surfacing a passage that cites a deprecated
code, cross-checked against the graph to confirm it's deprecated and what
replaced it — something neither store could do alone (OpenSearch/fulltext
would surface the passage but not know the code's current status; the graph
knows the status but isn't a text-search engine).

## 6. Honest caveats

- Today's corpus is **one file, three sections** (`general` KB) plus an
  **empty** `db` KB and a **not-yet-created** `vde` KB. Every relevance/
  latency conclusion below is only as meaningful as this tiny corpus allows
  — re-run this evaluation once
  [`docs/design/ROADMAP_CHECKLIST.md`](design/ROADMAP_CHECKLIST.md) item 5
  (VDE corpus, more DB Richtlinien) actually lands.
- The supersession-edge extraction (`extract_supersessions`) is a single
  regex pattern tuned to the one real sentence in the corpus today
  ("X, superseded YYYY by Y"). A larger corpus will very likely need either
  a more general pattern or (better, longer-term) a structured
  `deprecated_by:` field in the machine-readable block instead of prose
  regex-mining.
- The local embedding provider (`sentence-transformers`/`all-MiniLM-L6-v2`)
  pulls in `torch` — hundreds of MB, multi-minute install — the heaviest
  dependency added to this repo so far. Worth it for a zero-cost, offline
  PoC; worth reconsidering if `torch` ever becomes a deploy-size problem for
  Cloud Run.

## 7. Recommendation & roadmap

1. **Adopt OpenSearch as `rag.py`'s semantic-retrieval seam next** (the
   swap the codebase has been flagging since before this PoC —
   `README.md`, `docs/ARCHITECTURE.md`). It's the more general-purpose win:
   every existing `retrieve()` call site benefits immediately, `kb_ids`
   filtering carries over unchanged, and the local embedding provider keeps
   it free/offline. Wiring this in is explicitly **not done this
   iteration** — `rag.py` is unmodified — but `app/kb/opensearch_store.py`
   is ready to be called from it.
2. **Grow the Neo4j graph incrementally, not as a `rag.py` replacement.**
   Its value is the explicit relationships a similarity search structurally
   cannot express — start with the `(:Finding)-[:CITES]->(:Code)` edge
   forward-referenced in `neo4j_store.py`'s docstring, which would let a
   compliance report query "which of my findings currently cite a
   deprecated code" as a single Cypher traversal instead of a manual
   cross-check.
3. **Keep Cognee for what it's already good at** (opportunistic chat
   memory, zero extra infra) — it's not competing with this PoC's use case
   of deliberately comparable, `kb_ids`-scoped, browsable retrieval.
4. **Re-run this entire evaluation once the corpus grows** — cross-refs
   [`docs/design/ROADMAP_CHECKLIST.md`](design/ROADMAP_CHECKLIST.md) item 5
   (VDE corpus, more DB Richtlinien folders). Every relevance number above
   is provisional on a 1-document corpus.

## 8. Decision record

| Date | Decision | Why |
| :--- | :--- | :--- |
| 2026-07-30 | Stand up `docker-compose.kb.yml` (OpenSearch + Dashboards, Neo4j + Browser) as a local-only evaluation harness, separate from `deployment/Dockerfile` | Needed a real, running, hands-on comparison — not a paper exercise — without risking the production Cloud Run path |
| 2026-07-30 | Both stores ingest the same `backend/data/regulations/` folders via shared `app/kb/corpus.py` chunking (reused from `rag.py`, not reimplemented) | Fair apples-to-apples comparison; any relevance difference is attributable to retrieval method, not chunking |
| 2026-07-30 | Default embedding provider = local `sentence-transformers`, OpenAI opt-in | Matches this repo's established free/local-first bias; zero API cost for the PoC |
| 2026-07-30 | Fixed: OpenSearch needs `OPENSEARCH_INITIAL_ADMIN_PASSWORD` even with security disabled | Blocked container startup entirely until found |
| 2026-07-30 | Fixed: Neo4j ingestion was silently dropping `active_codes`/`deprecated_codes` (wrong chunk gating) | Caught by verifying `CITES` edge count against the known 4-code corpus, not assumed correct |
| 2026-07-30 | Verdict: adopt OpenSearch as the `rag.py` retrieval seam next; grow Neo4j incrementally for structured citation relationships; keep Cognee as-is | See §7 |
| 2026-08-17 | Added a parallel project-document corpus (extraction + indexing), not a regulation-corpus growth — see §9 | The real `dataset/raw/project_1/` deliverable set is structurally different from the regulation corpus (project docs, not compliance rules), so it gets its own chunker/schema rather than overloading `corpus.py`'s `active_codes`/supersession regex |

## 9. Project-document corpus (`dataset/raw/`) — extraction + indexing

Separate from everything above (§1–8 cover the *regulation* corpus,
`backend/data/regulations/`). This section covers indexing the real project
deliverable set at `dataset/raw/project_1/` (91 MB, 198 files across 9
substation folders) — a different kind of corpus (engineering deliverables,
not compliance rules), so it gets a parallel extraction step and its own
chunker/graph schema rather than being folded into `app/kb/corpus.py`.

### 9.1 Extraction — Docling, CPU-only feasibility (measured on this machine)

`app/ingestion/docling_pipeline.py` (`make docling-extract`) walks
`dataset/raw/<project>/` and writes folder-mirrored Markdown to
`dataset/clean/<project>/`, tiered by *measured* text density rather than a
folder-name whitelist:

- **Tier 1** (full Docling ML pipeline — layout + table-structure models):
  `.docx` always; `.pdf` when its `pdftotext` text layer has ≥50 real
  words. Measured **~15–22 s/page, ~2.1 GB peak RSS** on this laptop
  (i7-1165G7, 8 threads, 15 GB RAM, **no discrete GPU** — CPU-only
  confirmed workable, not fast). `pip install docling` (2.120.2) took
  ~4.5 min / ~5.5 GB standalone, but only ~20 s / ~0.4 GB *additional* in
  this repo's actual backend venv since `torch` is already installed for
  `sentence-transformers` (§2.1) and is shared.
- **Tier 2** (fast — `pdftotext -layout` only, no ML): everything else.
  Of the 184 PDFs in `project_1`, only 27 (the two Erläuterungsbericht
  narrative reports, the 9 Stromberdarfberechnung calc reports, and a
  subset of multi-page Erdungsanlage/Netzeinspeisung/Elektroinstallations-
  plan/Unterverteilung exports that carry real parts-list text) cleared
  the Tier-1 threshold — 187 pages, ~45–70 min of ML time. The rest are
  single-page CAD title-block exports with as little as 87 extracted
  characters (verified directly: full Docling on one of these produced a
  markdown file consisting of the title-block text plus `<!-- image -->`
  placeholders for the drawing itself) — Tier 2 handles these in
  low-single-digit seconds total instead of the ~20 s/page the full
  pipeline would otherwise burn on them for no benefit.
- Skipped outright (logged in `dataset/clean/<project>/_manifest.json`,
  not silently dropped): the 12 `.heic` site photos (no extractable text)
  and the 1 `.zip` (a redundant duplicate of an already-unzipped sibling
  folder — same files present twice in the raw dataset).
- Every output `.md` carries a small hand-written-YAML frontmatter block
  (`project`/`substation`/`category`/`source_path`/`tier`/`page_count`) —
  the single source of truth `app/kb/project_corpus.py` reads for both
  stores below. Parsed with a small hand-rolled reader matching its own
  writer's escaping (`docling_pipeline._yaml_str`), not PyYAML — the
  schema is fixed and self-controlled, so a full YAML parser dependency
  wasn't worth adding.

### 9.2 Indexing — parallel stores, reusing connection/embedding primitives

Regulation-specific `app/kb/opensearch_store.py` / `neo4j_store.py` are
tuned to that corpus's H2-only chunking and `(:Code)`/`CITES`/
`SUPERSEDED_BY` schema (§3.2) — not a fit for project documents. Added
parallel, additive modules instead:

- `app/kb/project_corpus.py` — splits Tier-1 Markdown on *any* heading
  level (Docling emits real nested structure, unlike the regulation
  corpus's flat H2 convention); Tier-2 stubs come through as one chunk.
- `app/kb/project_opensearch_store.py` — new index `rail50hz_project_docs`
  (separate from `rail50hz_regulations`), reuses
  `opensearch_store.embed()`/`embed_dims()`/`get_client()` rather than
  duplicating the embedding logic; adds `substation`/`category` keyword
  filters `query()` can scope by.
- `app/kb/project_neo4j_store.py` — additive schema, same Neo4j instance,
  different labels (no interaction with `:Code`):
  `(:Project)`, `(:Substation)-[:PART_OF]->(:Project)`,
  `(:Document)-[:BELONGS_TO]->(:Substation)`, `(:Document)-[:HAS_SECTION]->(:Section)`.
  Turns the folder taxonomy the client already uses into a real one-hop
  query — e.g. "every Erdungsanlage section for ESTW-A Dörstewitz" — the
  same graph-only value case §3.3 makes for regulation supersession
  chains, applied to the project corpus's own structure.
- `scripts/project_kb_ingest_opensearch.py` / `_neo4j.py` — same shape as
  the existing `kb_ingest_*.py` scripts; `make kb-ingest-project` runs
  both (reuses the already-running `make kb-up` stack, unmodified).
