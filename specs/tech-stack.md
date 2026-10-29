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
| Model access | `langchain-core`, `langchain-openai` (`langchain-anthropic` as an optional extra) | Any OpenAI-compatible endpoint by base URL, key and model, with structured output |
| Curation workflow | `langgraph` | Loops and conditional edges for propose, challenge and revise |
| arXiv | `arxiv` | Its client honors arXiv's one-request-per-three-seconds rule |
| OpenAlex | `pyalex` | API key, retries, `select`, filters and cursor pagination |
| Local files | `llama-index-core`, `llama-index-readers-file` | Reads PDF, DOCX, PPTX, EPUB, HTML, Markdown, notebooks, CSV and text. Runs only inside a sandboxed subprocess with an allowlist of readers |
| Scheduling | `python-crontab` | Finds, adds and removes jobs by comment (LGPL-3.0, used as a library) |
| Locking | `filelock` | One run per cluster at a time |
| Injection classifier | A local open-source model through `transformers`, chosen by a measured evaluation | Loaded from a pinned safetensors revision with remote code disabled. Until the evaluation is recorded, the input guard runs rules-only and `rkc doctor` warns |
| Hierarchical retrieval | LeanRAG, the published project at a pinned commit, unmodified | Runs through Docker (MySQL and Milvus) behind a three-method engine interface. Patches are applied only for failures a spike measured |

## Data
- **Claim store:** SQLite in WAL mode with foreign keys, one `store.sqlite` per cluster. It is append-only: rows are never updated except to close them (`closed_cs`, `released_at`). Changeset IDs are assigned only by the store.
- **History:** one time axis, the changeset sequence, with as-of reads. Claim status is derived from open evidence and links by a view and is never stored.
- **Keyword recall:** SQLite FTS5, kept in sync by the store. It serves curator recall and query fallback, and is not a retrieval engine. `rkc doctor` checks that FTS5 is available.
- **Migrations:** automatic, by `schema_version`. Opening a store with a newer schema fails clearly.
- **Raw cache:** hash-addressed payloads and normalized text, never edited. Cache keys come from hashes only.
- **Cluster layout:** `.rkc/<cluster>/` contains `cluster.yaml`, `agents/*.yaml`, the store, `raw/`, `engines/`, `runs/` and a lock. It is gitignored apart from the configuration files.

## Security architecture
- **Input guard (mandatory):** every article, metadata field and local file is scanned (normalization, recursive decoding, linear-time rules, and the classifier) before anything is stored. Content it detects is banned by hash and namespaced source ID, and the cache copy is deleted. Scanning fails closed.
- **Output guard (on by default):** query results are sanitized (markup, URLs, control, bidirectional and zero-width characters, length caps) and scanned. Flagged items are withheld and recorded.
- **Enforcement controls (the real defense):** curation agents have no tools. Prompts wrap outside text in a provenance-marked untrusted block. Every model output is structured, sanitized and capped. Quotes are verified mechanically. Approving an agent needs an interactive terminal. Source identity uses provider-controlled namespaced IDs (`arxiv:`, `openalex:`, `file:`), and DOIs are attributes only. File parsing and the LeanRAG build run sandboxed with an empty environment. `rkc pause` works as a kill switch.

## Testing policy
- Framework: `pytest`.
- **Test-first** for behavior: write the failing test, implement, then see it pass. Implementing first is fine only for wiring, types and configuration.
- **Offline by default.** Tests use scripted fake models, recorded API responses, a fake engine and a fake crontab backend. No test needs network, keys or Docker, except the LeanRAG contract tests, which need the services running and are marked so they can be skipped.
- Unit tests sit beside each module's concerns in `tests/`. Shared fixtures (a fixture cluster, recorded responses, a gold question set from `docs/topics.md`) live in `tests/fixtures/`.
- Security: `tests/security/corpus/` (poisoned and benign items, including benign research about prompt injection) and `tests/security/cases/` (smoke cases). The suite grades by observed effect, never by refusal wording, and reports errors as inconclusive.
- A phase is not done until its tests pass, its acceptance commands work, and lint, format check, type check and the full test suite pass.

## Quality tooling
- Lint: `uv run ruff check .`
- Format: `uv run ruff format --check .`
- Types: `uv run mypy --strict src/` (tests are type-checked with the default settings).
- Tests: `uv run pytest -q`
- CI: GitHub Actions runs lint, format check, type check and tests on Python 3.12 and 3.14 for every push and pull request.

## Constraints
- License: MIT. Every dependency's license must allow that, including the LGPL-3.0 `python-crontab` used as a library. A classifier model's license and download terms are checked before it becomes the default.
- Secrets live only in environment variables or `.env`, never in YAML, the store, logs or output. Messages name a missing key by its variable, never by its value.
- arXiv is limited to one request per three seconds on one connection. OpenAlex is optional, and without a key it is skipped with a notice rather than treated as an error.
- Docker is required for LeanRAG. Its services bind to localhost, with generated credentials in an owner-only file.
- `rkc` modifies nothing outside its cluster directory, crontab lines marked `rkc:`, and a skills directory the user names.
- Spend is bounded by two integer caps per agent: items and model calls.

## Project structure
- `src/research_knowledge_curator/`: one module per concern (`cli`, `config`, `store`, `cache`, `scan`, `llm`, `sources`, `curate`, `engines`, `engine_leanrag`, `run`, `schedule`).
- `docker/`: the LeanRAG compose file.
- `skills/`: `rkc-setup`, `rkc-query`, `rkc-ops`, `rkc-report`, installed into a host project by `rkc skills install`.
- `scripts/`: `scanner_eval.py`, `security_smoke.py`.
- `tests/`, `tests/fixtures/`, `tests/security/`.
- `docs/`: `topics.md`, `limits.md`, and `spikes/` for recorded spike results.
- `specs/`: this constitution, feature specs, and the backlog (including the archived design v3.1).
