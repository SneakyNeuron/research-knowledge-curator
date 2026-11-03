# Research Knowledge Curator

Agent-maintained, injection-defended research knowledge base. Working names: package `research-knowledge-curator`, CLI `rkc`.

Status: scaffolding. Nothing functional yet: `rkc` only reports its version (`rkc --version`, `rkc version [--json]`). The project follows Spec-Driven Development: the constitution is in `specs/mission.md`, `specs/tech-stack.md` and `specs/roadmap.md`, and feature specs go in `specs/features/`. The earlier design (v3.1) is archived in `specs/backlog/2026-10-28-design-v3.1.md` as input for feature specs; it predates the 2026-11-02 pivot from claim curation to original-text indexing, and the constitution wins where they differ. The owner's topics and draft example questions are in `docs/topics.md`.

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

## Acknowledgements

Retrieval in `rkc` follows LeanRAG, by Yaoze Zhang, Rong Wu, Pinlong Cai, Xiaoman Wang, Guohang Yan, Song Mao, Ding Wang and Botian Shi: "LeanRAG: Knowledge-graph-based generation with semantic aggregation and hierarchical retrieval", AAAI 2026 ([arXiv:2508.10391](https://arxiv.org/abs/2508.10391), code at [KnowledgeXLab/LeanRAG](https://github.com/KnowledgeXLab/LeanRAG)). `rkc` reimplements the published algorithm and contains no code from the upstream repository.

## License

MIT, see `LICENSE`.
