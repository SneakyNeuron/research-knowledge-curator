# Tech stack

## Runtime & language
- Python, supporting `>=3.12` for users and developed on 3.14 (`.python-version`). Every supported version is tested in CI.
- Managed with `uv`: `uv sync` for development and `uv tool install` for users. The build backend is `uv_build`.
- The distribution is `research-knowledge-curator` (import `research_knowledge_curator`), with console scripts `rkc` and `research-knowledge-curator`. Both names were free on PyPI on 2026-10-29.

## Frameworks & libraries
Exact versions are pinned in `pyproject.toml` and `uv.lock` when each dependency is introduced, after checking the current release on PyPI. This file records the choices, not the version numbers.

| Concern | Choice | Why |
|---|---|---|
| CLI | `typer` | Declarative commands, help text and a global `--json` option |
| Config and schemas | `pydantic`, `pyyaml` | Validation errors that name the file and field, and versioned schemas |
| Model access | `langchain-core`, `langchain-openai` (`langchain-anthropic` as an optional extra) | Any OpenAI-compatible endpoint by base URL, key and model, with structured output. Roles: relevance triage (one structured call per paper), and the engine's extraction, summary and embedding models. The engine calls models through this layer |
| arXiv | `arxiv` | Metadata and PDF download; its client honors arXiv's one-request-per-three-seconds rule |
| OpenAlex | `pyalex` | API key, retries, `select`, filters and cursor pagination. Full text only from OpenAlex's own content endpoint (metered, limited daily on a free key), never from publisher URLs in the metadata |
| Text extraction (PDF and local files) | `llama-index-core`, `llama-index-readers-file` | Owned by `scan`, as the first layer of the input guard. One path for downloaded PDFs and local files: PDF, DOCX, PPTX, EPUB, HTML, Markdown, notebooks, CSV and text. Runs only inside a sandboxed subprocess with an allowlist of readers |
| Scheduling | `python-crontab` | Finds, adds and removes jobs by comment (LGPL-3.0, used as a library) |
| Locking | `filelock` | One run per cluster at a time |
| Injection classifier | A local open-source model through `transformers`, chosen by a measured evaluation | Loaded from a pinned safetensors revision with remote code disabled. Until the evaluation is recorded, the input guard runs rules-only and `rkc doctor` warns |
| Hierarchical retrieval | LeanRAG (Zhang et al., "LeanRAG: Knowledge-graph-based generation with semantic aggregation and hierarchical retrieval", AAAI 2026, arXiv:2508.10391), reimplemented from the paper in the `engine_leanrag` subpackage | The upstream repository (KnowledgeXLab/LeanRAG) has no LICENSE file, so its code and prompts cannot be copied or redistributed, and it is unpackaged research scripts with a hard-coded MySQL server anyway. Our implementation follows the paper's algorithm (LLM entity and relation extraction, UMAP and Gaussian-mixture clustering, hierarchical summaries, lowest-common-ancestor retrieval) with our own code and prompts, and adds only: SQLite instead of MySQL, an embedded vector index instead of Milvus, configuration from `cluster.yaml`, and partial updates. It must reach parity with upstream's recorded behaviour under the outcome-based rule approved in phase 2. Its numeric dependencies (`numpy`, `scikit-learn`, `umap-learn`, `numba`, `tiktoken`) are default dependencies, pinned when the engine introduces them. It runs behind a three-method engine interface |

## Data
- **Intake store:** SQLite in WAL mode with foreign keys, one `store.sqlite` per cluster. It records sources (namespaced identity, metadata, content hashes, retraction flag), intake decisions with their relevance reason, runs and changesets, watermarks and the ban list. It does not hold claims; the text itself lives in the cache and the engine. It is append-only: rows are never updated except to close them (`closed_cs`, `released_at`). Changeset IDs are assigned only by the store.
- **History:** one time axis, the changeset sequence, with as-of reads. Each run that adds sources is one changeset, so a run can be retracted as a unit: its sources are closed in the store and removed from the engine at the next sync.
- **Notes seam:** the engine's lowest level is the original text of each source. Notes, when they arrive, attach to a source (and a location in it) as separate rows marked as notes; they never modify the cached text. The schema for notes is designed in the phase that introduces them.
- **Keyword fallback:** SQLite FTS5 over the normalized source text, kept in sync by the store. It serves query fallback when the engine is missing or stale, and is not a retrieval engine. `rkc doctor` checks that FTS5 is available.
- **Migrations:** automatic, by `schema_version`. Opening a store with a newer schema fails clearly.
- **Raw cache:** hash-addressed payloads (the downloaded PDF or file) and the extracted, normalized text, never edited. Cache keys come from hashes only. Results locate a passage in this text by source ID and offsets, so a verbatim passage can always be checked against the cache.
- **Engine store:** LeanRAG's graph (entities, relations, hierarchy, generated summaries, chunk records) lives in its own SQLite file, `engines/leanrag/graph.sqlite`, separate from the intake store. It is derived and disposable: updated in place by partial updates and rebuildable at any time from the store and the cache. Its vectors use an embedded index (no server) that works on Linux, macOS and Windows; the index (Milvus Lite 3.x, `sqlite-vec` or brute force) is chosen in the phase that builds the engine. Every chunk keeps its source ID and offsets into the cached text, so a verbatim result can be checked against the cache.
- **Engine updates:** each sync applies a partial update: new sources are chunked, extracted and attached to the nearest existing clusters, retracted sources are removed, and only the ancestors of changed nodes are re-summarized. A full rebuild happens only on explicit request (`rkc engine rebuild`). `rkc engine status` reports how far the hierarchy may have drifted (for example, updates since the last rebuild) so an agent can decide when to rebuild.
- **Cluster layout:** `.rkc/<cluster>/` contains `cluster.yaml`, `agents/*.yaml`, the store, `raw/`, `engines/`, `runs/` and a lock. It is gitignored apart from the configuration files.

## Security architecture
- **Input guard (mandatory):** every metadata field, every extracted full text (including text hidden outside the visible PDF page) and every local file is scanned (normalization, recursive decoding, linear-time rules, and the classifier) before anything is stored or indexed, and before the relevance model reads it. Content it detects is banned by hash and namespaced source ID, and the cache copy is deleted. Scanning fails closed.
- **Output guard (on by default):** query results are sanitized (markup, URLs, control, bidirectional and zero-width characters, length caps) and scanned. Flagged items are withheld and recorded. Every result is labelled as verbatim source text (with source ID and offsets, checkable against the cache) or as engine-generated text (LeanRAG's summaries), never mixed.
- **Enforcement controls (the real defense):** the relevance model has no tools and its output is a structured decision (relevant or not, a capped reason) that cannot change what is stored beyond accept or reject. Prompts wrap outside text in a provenance-marked untrusted block. Every model output is structured, sanitized and capped. Downloads come only from provider-controlled endpoints built from namespaced IDs, never from URLs found in fetched content. Approving an agent needs an interactive terminal. Source identity uses provider-controlled namespaced IDs (`arxiv:`, `openalex:`, `file:`), and DOIs are attributes only. File parsing runs sandboxed with an empty environment. The engine runs in-process as our own reviewed code: its model calls (extraction and summaries) have no tools, take untrusted text only inside a provenance-marked block, and return structured, capped output; nothing from papers or model output builds a path, SQL statement or configuration (parameterized SQL, keys from hashes and namespaced IDs only); its summaries are always labelled generated. `rkc pause` works as a kill switch.

## Testing policy
- Framework: `pytest`.
- **Test-first** for behavior: write the failing test, implement, then see it pass. Implementing first is fine only for wiring, types and configuration.
- **Offline by default.** Tests use scripted fake models, recorded API responses, a fake engine and a fake crontab backend. No test needs network, keys or Docker; engine tests use a scripted fake model and deterministic fake embeddings. Enforced by `pytest-socket` (`--disable-socket` in the pytest configuration).
- Unit tests sit beside each module's concerns in `tests/`. Shared fixtures (a fixture cluster, recorded responses, a gold question set from `docs/topics.md`) live in `tests/fixtures/`.
- Security: `tests/security/corpus/` (poisoned and benign items, including benign research about prompt injection) and `tests/security/cases/` (smoke cases). The suite grades by observed effect, never by refusal wording, and reports errors as inconclusive.
- A phase is not done until its tests pass, its acceptance commands work, and lint, format check, type check and the full test suite pass.

## Quality tooling
- Lint: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Types: `uv run mypy --strict src/` and `uv run mypy tests/` (tests are type-checked with the default settings).
- Tests: `uv run pytest -q`
- All of the above in one command: `scripts/check.sh`, which also runs the tests under CI's colour variables (`GITHUB_ACTIONS`, `FORCE_COLOR`, `PY_COLORS`).
- CI: GitHub Actions runs the same commands as local (lint, format check, both type checks and tests) on Python 3.12 and 3.14 for every push and pull request.

## Constraints
- License: MIT. Every dependency's license must allow that, including the LGPL-3.0 `python-crontab` used as a library. No LeanRAG code or prompt text from the upstream repository is copied into `rkc` (it has no license): reading it to understand behaviour is fine, copying or closely paraphrasing it is not, and prompts are written fresh. `engine_leanrag/PROVENANCE.md` cites the paper, links the upstream repository and the commit compared against, maps each part of the paper to our module, and records every deliberate departure from the paper with its measured reason. The README credits the authors. A classifier model's license and download terms are checked before it becomes the default.
- Secrets live only in environment variables or `.env`, never in YAML, the store, logs or output. Messages name a missing key by its variable, never by its value.
- arXiv is limited to one request per three seconds on one connection, PDF downloads included. OpenAlex is optional, and without a key it is skipped with a notice rather than treated as an error. OpenAlex full-text downloads are metered, so they count against the agent's item cap and fall back to the abstract when the daily allowance is used up.
- Full texts keep their original copyright. They are cached locally for the user's own research and never redistributed by `rkc`.
- No services to run: everything except the model endpoints and the sources is embedded (SQLite files and an embedded vector index). Supported on Linux, macOS and Windows wherever the pinned dependencies publish wheels.
- `rkc` modifies nothing outside its cluster directory, crontab lines marked `rkc:`, and a skills directory the user names.
- Spend is bounded by two integer caps per agent: items and model calls. Full-text size is capped before extraction and before indexing, which also bounds the engine's extraction and summary cost.

## Project structure
- `src/research_knowledge_curator/`: one module per concern (`cli`, `config`, `store`, `cache`, `scan`, `llm`, `sources`, `triage`, `engines`, `engine_leanrag`, `run`, `schedule`). `engine_leanrag` is a subpackage holding our LeanRAG reimplementation and its `PROVENANCE.md`.
- `skills/`: `rkc-setup`, `rkc-query`, `rkc-ops`, `rkc-report`, installed into a host project by `rkc skills install`.
- `scripts/`: `check.sh` (every quality gate, plus the tests under CI's colour variables), `scanner_eval.py`, `security_smoke.py`, and `spikes/leanrag/` (the throwaway harness that runs upstream LeanRAG unmodified for the baseline, removed once our engine reaches parity).
- `tests/`, `tests/fixtures/` (including `leanrag_baseline/`, the phase 2 parity baseline), `tests/security/`.
- `docs/`: `topics.md`, `limits.md`, and `spikes/` for recorded spike results.
- `specs/`: this constitution, feature specs, and the backlog (including the archived design v3.1, which predates the 2026-11-02 pivot from claim curation to original-text indexing; the constitution wins where they differ).
