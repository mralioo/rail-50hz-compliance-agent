# Document Extraction (`documents` bounded context)

Converts the raw project corpus (`dataset/raw/<project>/` — German DB railway 50 Hz
submittals: PDFs of schematics, electrical plans, earthing/lightning-protection
drawings, current-demand calculations) into a folder-mirrored corpus of Markdown +
image artifacts under `dataset/clean/<project>/`, via a remote Docling server. This
is the feature that feeds `app/kb/project_corpus.py` (chunking into the KB stores) and,
looking ahead, will feed the compliance-analysis agent (`app/agent/`, MIGRATION_MAP row 4)
once that context reads project documents instead of only regulation text.

See `docs/architecture/README.md` for the backend's overall DDD/hexagonal layering and
`docs/architecture/MIGRATION_MAP.md` row 11 for this slice's migration-map entry and the
naming-reconciliation note (this slice was first built copying `reference_codebase/`'s
ITUKI folder names verbatim, then renamed to this repo's own `adapters/`-not-`infrastructure/`
convention — read that note before copying anything else out of `reference_codebase/`).

## Why a remote server, not a local pipeline

An earlier version of this feature ran Docling's ML pipeline locally (CPU-only,
~15-22s/page) with a two-tier fallback (full ML pipeline vs. a `pdftotext` stub) to
keep CPU cost down. It's gone — this project has a Docling server available
(`DOCLING_BASE_URL`, default `http://10.0.1.236/docling`, the same server the sibling
ITUKI backend uses), so every file gets the full pipeline (layout, table structure,
OCR, image extraction, picture classification) with no local ML dependency at all —
`app/adapters/documents/` needs only `httpx` (HTTP) and `Pillow` (image cropping).

## Architecture

```
scripts/docling_ingest.py                              (CLI — batch, one project)
scripts/smoke_test_extraction.py                        (CLI — one real file, quality report)
        │
        ▼
app/application/documents/dataset_ingestion_service.py  walks dataset/raw/<project>,
                                                          classifies, bounds concurrency,
                                                          writes _manifest.json
        │
        ▼
app/application/documents/ingest_pipeline.py             assembles + runs the pipeline
                                                          for one file (IngestDocumentContext)
        │
        ▼
app/pipelines/  (generic engine, no document-specific logic)
        │  Pipeline(ConvertDocumentStep, StoreFileStep,
        │           BestEffortPipelineStep(StoreExtractedImagesStep),
        │           WriteExtractedTextArtifactStep)
        ▼
app/application/shared_steps/document_steps.py            the four steps above — each
                                                          calls a domain port, never an
                                                          adapter directly
        │
        ▼
app/domain/documents/{models.py,ports.py,storage_keys.py,services.py}   pure, framework-free
        │  DocumentConversionClientPort, DocumentTextExtractionPort, FileStoragePort
        ▼
app/adapters/documents/{docling_client.py, docling_conversion_adapter.py,
                        docling_text_extraction_adapter.py,
                        local_file_storage_adapter.py}     the "how" — Docling HTTP + local disk
        │
        ▼
app/bootstrap.py    get_document_conversion_client() / get_document_text_extraction_client()
                     / get_document_file_storage(root) — the only place that imports the
                     adapter classes above
```

Two rail-specific modules sit beside the ported steps (not part of `reference_codebase/`,
since ITUKI has S3+Postgres and doesn't need either):

- `app/application/documents/local_keys.py` — artifact key layout. This project has no
  document database, so instead of ITUKI's `storage_keys.py` convention (UUID-keyed,
  `projects/{id}/documents/{id}/...`, ported anyway to `app/domain/documents/storage_keys.py`
  for a future DB-backed deployment but **not currently used**), documents are keyed by their
  *source-relative path* so `dataset/clean/` mirrors `dataset/raw/` and is human-browsable:
  ```
  <rel_path>.md                                   extracted text artifact (the KB's input)
  <rel_path>/raw/<filename>                        raw binary artifact
  <rel_path>/images/<NNN>_p<PP>_<sha8>.png          extracted images, in document order
  ```
- `app/application/documents/markdown_artifact.py` — renders the final `.md`: YAML
  frontmatter (the contract `app.kb.project_corpus` parses — `project`/`substation`/
  `category`/`source_path`/`tier`/`page_count`/`image_count`), chunk text reassembled in
  page+index order, `<!-- image -->` placeholders replaced in document order with links to
  the extracted images, and an "Extracted images" reference table (page, file, predicted
  type, caption). Every extracted image always gets a table row and a working link —
  inline `![picture N]` links only appear where Docling's chunker actually placed a
  `<!-- image -->` marker in the flowing text. A running header/footer logo has no such
  anchor (Docling treats it as page furniture, not body content), so it shows up in the
  table only — observed on a 61-page report where 63/65 extracted images were the
  repeated company letterhead logo, correctly classified `logo`, all present and linked
  in the table with zero inline anchors. Not a bug — just no natural inline position for
  a repeating page decoration.

## AEC tuning

`app/adapters/documents/docling_conversion_adapter.py` defaults reflect this corpus, not
generic documents: German+English OCR (`ocr_lang=["de","en"]`), picture classification on,
2x page-render scale (schematics stay legible when cropped), `dlparse_v4` PDF backend,
accurate table mode. `--force-ocr` and `--describe-pictures` (with an AEC-specific VLM
prompt baked into the adapter) are opt-in CLI flags for harder cases — see next section.

## Running it

**One-time setup** (no `backend/.venv` exists yet in this repo — create it before the
`make` targets below work):
```bash
make setup   # creates backend/.venv, installs backend/requirements.txt
```

**Batch — a whole project:**
```bash
make docling-extract PROJECT=project_1
# or directly:
cd backend && .venv/bin/python scripts/docling_ingest.py --project project_1 \
    [--force] [--limit N] [--concurrency N] [--base-url URL] \
    [--force-ocr] [--images-scale 2.0] [--describe-pictures] [-v]
```
- `--concurrency N` (default 1): files converted in parallel against the server. Each
  conversion is a slow network round trip (OCR + layout + rendering — measured
  10-40s/file on this corpus), so sequential on ~185 files is a multi-hour job;
  concurrency shortens that roughly proportionally, bounded by server capacity. Verified
  with a synthetic delay test: concurrency=4 over 8 slow "files" ran in ~1 batch-time
  instead of 8x sequential, with exactly 4 in flight at once and manifest order preserved.
- `--limit N`: cap convertible files processed — use for a quick check before a full run.
- `-v`: per-file progress logging (converted/failed + timing), not just the final summary.
- Incremental by default: a file already converted with an up-to-date artifact is skipped
  (`--force` to reconvert everything).

**One real file — quality check:**
```bash
cd backend && .venv/bin/python scripts/smoke_test_extraction.py [--file PATH] \
    [--base-url URL] [--force-ocr] [--describe-pictures] [--print-markdown]
```
Defaults to a real schematic from `dataset/raw/project_1` if `--file` is omitted. Prints
chunk/char/image counts, every extracted image's page/dimensions/predicted
type/caption, and (`--print-markdown`) the full rendered artifact — this is how you judge
extraction quality on a new document without touching `dataset/clean/`.

## Full run results (project_1, 2026-09-16, `--concurrency 4`)

```
198 file(s) in 1365.8s (~22.8 min)
by status: {'ok': 185, 'skipped': 13}
images extracted: 401
chunks extracted: 572
errors: 0
```

13 skipped: 12 `.heic` (site photos, no text), 1 `.zip` (redundant archive) — as designed.
Output: 152 MB under `dataset/clean/project_1/` (56 MB input) — expect roughly 3x growth
from full-page-render crops. 135/185 files got at least one image (401 total); the other
50 got zero, concentrated exactly where the vector-schematic limitation below predicts —
Erdungsanlage (13), Netzersatzanlage (12), Übersichtsschema (6), Kabellageplan (5),
Netzeinspeisung (4) — categories that are plan/schematic drawings, not photos or scanned
pages. Zero conversion errors across the full corpus.

## Known limitations

- **Vector-line schematics aren't always detected as a "picture."** Verified on
  `ESTW_A Ilmenau/Übersichtsschema/1633028233_Info.pdf`: Docling's layout model
  correctly cropped and OCR'd the title-block/legend (readable German text, correctly
  positioned), but the actual single-line diagram — pure vector line art — wasn't tagged
  as a distinct picture region at all, so it never gets its own cropped image. This is a
  layout-model limitation on CAD-style vector content, not a bug in this pipeline. Not
  fixed yet — a possible follow-up is a whole-page-render fallback (save the full page
  too when a page has zero detected pictures), traded off against extra storage.
- **`.docx` pictures are detected but never cropped.** Observed live during the
  project_1 full run: `Erläuterungsbericht.docx` — Docling found 4 pictures
  (`document.pictures`) but extracted 0 of them ("extracted 0 / 4 picture(s)"). The
  crop logic in `docling_conversion_adapter.py` needs `document.pages[N].image.uri`
  (a rendered page raster) to crop from, which is a PDF-pipeline artifact — DOCX
  conversion doesn't produce page renders the same way, so every picture is skipped
  for lack of a source to crop from. Text extraction from `.docx` is unaffected (18
  chunks extracted from that file); only its embedded images are lost. Not fixed —
  would need either a DOCX-specific extraction path or converting DOCX -> PDF
  server-side first.
- **`app/bootstrap.py` eager-imports `ezdxf`.** Importing `app.bootstrap` for documents
  wiring only (e.g. from a minimal venv) transitively imports the `cad` context's adapters
  too, since bootstrap.py's CAD section constructs all four engines eagerly at module
  import time. Harmless in the real dev venv (ezdxf is already a backend dependency), but
  worth knowing if a lighter-weight consumer of `get_document_*` ever needs to avoid it —
  would need CAD's eager dict to become lazy factories first (out of scope here).
- **This dev box had a path-MTU blackhole** to the Docling server (large multipart uploads
  stalled — `WriteTimeout`/`ReadError`) — fixed via `sudo ip link set dev eth0 mtu 1380`.
  If large-file conversions mysteriously hang again after a reboot, check that first.

## Extension points (for the next feature/service)

The point of the port/adapter split is that the next few features are additive, not
rewrites:

- **Swap local disk for S3/Garage**: implement `FileStoragePort`
  (`app/domain/documents/ports.py`) against the real backend, wire it in
  `app/bootstrap.py::get_document_file_storage`. Nothing in `app/application/` or
  `app/domain/` changes. `storage_keys.py` (already ported, currently unused) is the
  ready-made key convention for that move — `local_keys.py`'s source-path-mirrored keys
  would need a real `Document` id (from a DB) at that point instead.
- **Embedding + vector store (RAG over project documents)**: `reference_codebase/`'s
  `EmbedAndIndexStep` is the pattern to port — a new step after
  `WriteExtractedTextArtifactStep` that embeds `context.text_chunks` and calls a new
  `VectorStorePort`. This repo already has an OpenSearch/Neo4j evaluation harness for the
  *regulation* corpus (`app/kb/`, `docs/OPENSEARCH_NEO4J_EVALUATION.md`) — the natural next
  step is pointing an equivalent adapter at `context.text_chunks` here instead of building
  a new one from scratch.
- **Picture description (VLM captions)**: the port already supports it —
  `describe_pictures=True` on `get_document_conversion_client(...)` asks the Docling
  server's own VLM pipeline to caption each picture using the AEC-specific prompt already
  in `docling_conversion_adapter.py`. If a *separate* description model (not Docling's
  built-in one) is ever wanted, add an `ImageDescriptionClientPort` + adapter — pattern is
  in `reference_codebase/backend/domain/data/documents/ports/image_description_client.py`.
- **Compliance agent reading project documents**: once `app/agent/` migrates to
  `app/domain/compliance/` (MIGRATION_MAP row 4), it can depend on `DocumentConversionClientPort`
  the same way this slice does, or simply read the `.md` artifacts this pipeline already
  produces — no new port needed for read-only consumption.
- **A document database** (if project/document/chunk metadata ever needs querying,
  not just KB chunking): `reference_codebase/backend/domain/data/documents/ports/
  document_repository.py` is the port shape to port; `make_document_id()` in
  `ingest_pipeline.py` would need to change from a deterministic path-derived string to a
  real minted id at that point (it's deterministic today specifically *because* there's no
  DB to persist an id mapping in).

## Files changed/added (2026-08-21)

```
app/domain/documents/{models.py,ports.py,storage_keys.py,services.py}
app/adapters/documents/{docling_client.py,docling_conversion_adapter.py,
                        docling_text_extraction_adapter.py,local_file_storage_adapter.py}
app/pipelines/*.py                                  (generic engine: Pipeline, PipelineStep,
                                                      AsyncPipelineStep, PipelineCursor,
                                                      PipelineError, Best-Effort/Retry wrappers)
app/application/shared_steps/{contexts.py,document_steps.py}
app/application/documents/{ingest_pipeline.py,dataset_ingestion_service.py,
                           local_keys.py,markdown_artifact.py}
app/bootstrap.py                                    (+ documents wiring)
app/core/config.py                                  (+ docling_base_url, docling_chunk_max_tokens,
                                                      docling_images_scale, embedding_model)
backend/.env.example, backend/requirements.txt      (+ DOCLING_*/EMBEDDING_MODEL, + Pillow)
scripts/docling_ingest.py                           (rewritten: batch CLI, --concurrency)
scripts/smoke_test_extraction.py                    (new: single-file quality-check CLI)
docs/architecture/MIGRATION_MAP.md                  (+ row 11, naming-reconciliation note)

removed: app/ingestion/{docling_client.py,docling_images.py,docling_pipeline.py}
         (superseded — app/ingestion/{converter.py,storage.py,writer.py}, the unrelated
         DWG/DXF conversion + upload-staging code, is untouched)
```

## Refinement layer (`dataset/clean` → `dataset/super_clean`) — 2026-09-17

A second, optional stage on top of extraction: raw Docling output still carries real
extraction noise (OCR artifacts, repeated boilerplate/headers, broken line-wraps), and
every extracted image only had Docling's own coarse picture-classification label
(`table`/`logo`/`picture`) — not enough signal for good embedding/clustering. This layer
sends each document's text through an LLM for cleanup and each image through the same
LLM's vision capability for a description + category, writing the result to
`dataset/super_clean/<project>/` (mirrors `dataset/clean/`'s structure exactly; images are
**not** duplicated — links point back into `dataset/clean/.../images/`).

### Architecture

Same `documents` bounded context, same layering as extraction:

```
scripts/docling_refine.py                                (CLI — batch, one project)
        │
        ▼
app/application/documents/dataset_refinement_service.py   walks dataset/clean/<project>,
                                                            bounds concurrency, writes
                                                            _manifest.json
        │
        ▼
app/application/documents/refine_pipeline.py               assembles + runs the pipeline
                                                            for one file (RefineDocumentContext)
        │
        ▼
Pipeline(RefineTextStep, BestEffortPipelineStep(DescribeImagesStep),
         WriteSuperCleanArtifactStep)                       — app/application/shared_steps/
                                                              refinement_steps.py
        │
        ▼
app/domain/documents/ports.py   TextRefinementPort, ImageDescriptionPort
        │
        ▼
app/adapters/documents/{vllm_generative_client.py, vllm_text_refinement_adapter.py,
                        vllm_image_description_adapter.py}
        │
        ▼
app/bootstrap.py   get_text_refinement_client() / get_image_description_client()
```

**LLM**: the same server as Docling/embeddings — `google/gemma-4-31B-it` via vLLM,
nginx-proxied at `/generative/` (`VLLM_GENERATIVE_BASE_URL`). Verified multimodal: a real
extracted floor-plan crop got an accurate description correctly reading German room labels
("Rechnerraum", "Netzersatzraum", "TK-Raum") straight off the image.

### Text cleanup (`RefineTextStep` / `VllmTextRefinementAdapter`)

One LLM call per document, over its full body (not per-chunk) — Gemma's 131k-token context
comfortably covers this corpus (largest raw body measured: ~242k chars ≈ 60k tokens), so no
chunking is needed; a defensive `_MAX_INPUT_CHARS = 120_000` truncation guards against a
future, larger outlier. The prompt explicitly forbids summarizing, shortening, translating,
or adding commentary — this is cleanup, not rewriting. Any existing inline
`![picture N](...)` links are converted to `<!-- image N -->` markers **before** cleanup
(an LLM asked to "clean" text can't be trusted to leave markdown link syntax untouched) and
the model is instructed to preserve them verbatim; `WriteSuperCleanArtifactStep` resolves
survivors back to real descriptions afterward.

**Verified on the largest document** (65 images, 242,330-char body, truncated to 120,000):
cleaned output was 34,695 chars — a large shrink, checked for correctness rather than
assumed: the raw body has "Logo" repeated 63 times, several headers/phrases repeated
9–30 times (real duplicated boilerplate across a 61-page report), so the shrink is
legitimate repetition removal, not lossy summarization. Spot-checked the cleaned title
page/revision-history table/table-of-contents directly — accurate, nothing fabricated.

### Image description (`DescribeImagesStep` / `VllmImageDescriptionAdapter`)

One vision call per image, against a fixed, corpus-grounded category taxonomy (see
`CATEGORIES` in the adapter): `single_line_diagram`, `floor_plan`,
`electrical_installation_plan`, `earthing_lightning_protection`, `cable_routing_plan`,
`site_plan`, `title_block`, `table`, `logo_letterhead`, `photo`, `other`. Per-image failures
are caught individually (one bad image must not lose descriptions for the rest of the
document).

**Gotcha hit and fixed**: tried vLLM's `guided_json` first (to force
`{"description": ..., "category": ...}` output) — this server/model combination **silently
ignores it**, no error, just answers in ordinary prose as if the parameter weren't sent.
Switched to a plain `DESCRIPTION: ...` / `CATEGORY: ...` two-line format instead, parsed
with a regex — reliable regardless of guided-decoding support. `VllmGenerativeClient.chat()`
still accepts `guided_json` as a passthrough in case a future server/model actually honors
it, but callers shouldn't rely on it today.

**Real finding**: in this corpus, **zero documents have inline `![picture N]` markers** —
every extracted image is Docling "furniture" (a repeated logo, a title block) with no
natural inline anchor point in the flowing text. So today, descriptions only surface in each
document's "Extracted images" reference table, not inline in the body — the inline
marker-substitution code path (`refine_markdown.inline_descriptions`) is implemented and
unit-tested but isn't exercised by any real file in this corpus.

### Output

Same frontmatter contract as `dataset/clean/` (parsed via the now-shared,
public `app.application.documents.markdown_artifact.parse_frontmatter` — moved out of a
private copy in `app.kb.project_corpus`) plus one added field, `refinement_model`. Example:

```markdown
---
project: "project_1"
substation: "ESTW-A Dörstewitz"
category: "Aufstellplan 50 Hz"
source_path: "20250413_Abgabe50Hz_Strecke5919/ESTW-A Dörstewitz/Aufstellplan 50 Hz/2333116241_Info.pdf"
tier: 1
page_count: 1
image_count: 2
refinement_model: "google/gemma-4-31B-it"
---
<cleaned body text>

## Extracted images

| # | file | category | description |
| - | ---- | -------- | ----------- |
| 0 | [000_p001_a700b2a3.png](../../../../../clean/project_1/.../images/000_p001_a700b2a3.png) | floor_plan | A floor plan showing the layout of a "Rechnerraum", "Netzersatzraum LST-Anlage", "Flur", and "TK-Raum"... |
```

### Full run results (project_1, 2026-09-17, `--concurrency 4`)

```
184 file(s) in 666.6s (~11.1 min)
by status: {'ok': 184}
images described: 323/327
```

184/184 documents succeeded (0 errors). 4/327 images (1.2%) failed with `413 Request
Entity Too Large` — nginx's `/generative/` location has no `client_max_body_size`
override (unlike `/docling/`'s explicit `50M`), so its default (1M) rejects the
~2.3–2.8MB PNGs among this corpus's largest full-page renders once base64-encoded
(~33% larger again). Caught per-image (`DescribeImagesStep`'s per-item try/except) —
those 4 documents still completed with every other image described; not fixed
(would need either a nginx config change on the shared server or a client-side
downscale-before-describe step for oversized images).

### Running it

```bash
make docling-extract PROJECT=project_1          # first, if not already done
make docling-refine PROJECT=project_1 FLAGS="--concurrency 4 -v"
# or directly:
cd backend && .venv/bin/python scripts/docling_refine.py --project project_1 \
    [--force] [--limit N] [--concurrency N] [--base-url URL] [-v]
```

`--concurrency` bounds documents processed in parallel against the **same shared
generative server** other services on that box also use (chat-service, the ITUC app) — keep
it modest. Incremental by default (`--force` to redo everything).

### Wired into the KB stores

`app.kb.project_corpus` / `project_opensearch_store.py` now read from either
`dataset/clean/` or `dataset/super_clean/` (a `--source` flag / `SOURCE=` Makefile
variable) — built concurrently in a sibling session while this layer was being validated,
coordinated live to avoid file conflicts (see the session's cross-session messages). Once a
`make docling-refine` run completes, `make reindex-refined PROJECT=project_1` re-embeds the
LLM-cleaned+described corpus into OpenSearch and re-exports to Embedding Atlas in one step.
