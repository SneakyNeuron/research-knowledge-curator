# Research Knowledge Curator

Agent-maintained, evidence-anchored research knowledge base. Working names: package `research-knowledge-curator`, CLI `rkc`.

Status: scaffolding. Nothing functional yet: `rkc` only reports its version (`rkc --version`, `rkc version [--json]`). The project follows Spec-Driven Development: the constitution is in `specs/mission.md`, `specs/tech-stack.md` and `specs/roadmap.md`, and feature specs go in `specs/features/`. The earlier design (v3.1) is archived in `specs/backlog/2026-10-28-design-v3.1.md` as input for feature specs. The owner's topics and draft example questions are in `docs/topics.md`.

## Install

Not yet published on PyPI. Once it is:

```sh
uv tool install research-knowledge-curator
```

This installs two equivalent commands, `rkc` and `research-knowledge-curator`.

## Development

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 or newer is supported; development uses 3.14 (`.python-version`).

```sh
uv sync                        # create .venv with dev tools
uv run ruff check .            # lint
uv run ruff format --check .   # format check
uv run mypy --strict src/      # type check the package
uv run mypy tests/             # type check the tests
uv run pytest -q               # tests (offline; network access is blocked)
```

Secrets go in the environment or a local `.env` (see `.env.example`), never in YAML or the repository.

## License

MIT, see `LICENSE`.
