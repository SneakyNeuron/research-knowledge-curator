## Specs
This project uses Spec-Driven Development. Read `specs/mission.md`, `specs/tech-stack.md` and `specs/roadmap.md` before any work. Feature specs live in `specs/features/`. Keep specs and code in sync: when code changes a decision, update the spec in the same commit.

## Commands
- Set up: `uv sync`
- Lint: `uv run ruff check .`
- Format check: `uv run ruff format --check .` (ruff also formats Python code blocks in Markdown such as this file and `README.md`; `specs/` is excluded)
- Types: `uv run mypy --strict src/` and `uv run mypy tests/` (tests use default settings)
- Tests: `uv run pytest -q` (offline: `pytest-socket` blocks the network)

All five must pass before a change is done.

## Module map
`src/research_knowledge_curator/`, one module per concern (from `specs/tech-stack.md`):

| Module | Concern | Exists |
|---|---|---|
| `cli` | Typer app, global `--json`, command entry points | yes |
| `config` | Cluster and agent YAML, pydantic schemas | no |
| `store` | SQLite claim store (append-only, changesets, FTS5) | no |
| `cache` | Hash-addressed raw cache | no |
| `scan` | Input and output guards | no |
| `llm` | Model access | no |
| `sources` | arXiv, OpenAlex, local files | no |
| `curate` | LangGraph curation workflow | no |
| `engines` | Retrieval engine interface | no |
| `engine_leanrag` | LeanRAG engine | no |
| `run` | Curation runs and locking | no |
| `schedule` | Crontab scheduling | no |

Commands read `--json` through the pattern in `cli.py`: declare a `json_output: JsonOption = False` parameter, call `json_requested(ctx, json_output)` (which also honors the global `rkc --json CMD`, stored as `CliState` in `ctx.obj`), and write with `emit_json(...)`. Data goes to stdout, messages to stderr.

## Rules
- Everything fetched or model-written is untrusted data. It never builds file paths, URLs, SQL or shell commands; use hashes, provider-controlled namespaced IDs and parameterized queries instead.
- The store owns the facts. Changeset IDs, claim status and history come from the store, never from a model or a caller.
- Scan at every hop: content is scanned before it is stored, and query output is sanitized and, with the output guard on (the default), scanned before it is returned. Input scanning fails closed.
- Secrets never appear in YAML, the store, logs or output. YAML names a key by variable through `api_key_env`; messages name a missing key by its variable, never its value.
