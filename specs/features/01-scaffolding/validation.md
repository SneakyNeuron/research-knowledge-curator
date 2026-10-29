# Phase 01: Scaffolding — Validation

## Automated
- [x] V1 (R1): `uv run pytest -q` passes, including a test that `rkc --version` prints `rkc <version>` on stdout and exits 0, where `<version>` equals `[project] version` read from `pyproject.toml` with `tomllib`.
- [x] V2 (T3): `grep -rnE '[0-9]+\.[0-9]+\.[0-9]+' src/` finds no hard-coded version string.
- [x] V3 (R2, T9): tests assert that `rkc version --json` and `rkc --json version` each put a single line on `result.stdout` that `json.loads` parses to `{"version": "<version>"}`, with empty `result.stderr` and exit 0, and that plain `rkc version` prints `rkc <version>` (not JSON).
- [x] V4 (R3): a test asserts `rkc --help` lists `--version`, `--json`, `--help` and exactly one command, `version`, and no `--install-completion` or `--show-completion`.
- [x] V5 (R4): a test asserts bare `rkc` and `rkc --json` print the help text on `result.stdout` and exit 2.
- [x] V6 (R5): a test reads `pyproject.toml` with `tomllib` and asserts `rkc` and `research-knowledge-curator` map to the same entry point.
- [x] V7 (T4): `uv run ruff check .` and `uv run ruff format --check .` report no issues, with the rule set from T4 configured in `pyproject.toml`.
- [x] V8 (T5): `uv run mypy --strict src/` and `uv run mypy tests/` report no errors.
- [x] V9 (T1, T2): `uv sync --locked` succeeds; `pyproject.toml` has the bumped `uv_build` range, `requires-python = ">=3.12"`, `typer` as the only runtime dependency, and `pytest`, `pytest-socket`, `ruff`, `mypy` in the `dev` group, each pinned; `uv.lock` is committed.
- [x] V10 (T1): `uv run --isolated --python 3.12 pytest -q` passes, leaving the development `.venv` on 3.14.
- [x] V11 (T8): `uvx --from actionlint-py actionlint .github/workflows/ci.yml` and `uvx zizmor --offline .github/workflows/ci.yml` report no findings.
- [x] V12 (T7): the pytest configuration contains `--disable-socket`, and a test that tries to open a socket confirms it is blocked; no test reads keys or calls Docker.
- [x] V13 (R5, plan edge case): `uv run research-knowledge-curator --version` prints the same line as `uv run rkc --version`.
- [x] V14 (T9, plan edge case): a test asserts `rkc --bogus` exits non-zero with a usage error on `result.stderr` and empty `result.stdout`.

## Manual (human in the loop)
- [ ] M1 (T8): after pushing `feature/01-scaffolding` to `origin`, the CI workflow is green for both Python 3.12 and 3.14 on GitHub, and each job's log shows it ran on its matrix Python version (not the `.python-version` 3.14).
- [ ] M2 (T8): read `.github/workflows/ci.yml` and confirm it triggers on `push` and `pull_request`, the matrix is Python 3.12 and 3.14 passed to setup-uv's `python-version`, every `uses:` line is a 40-character SHA with a version comment, checkout has `persist-credentials: false`, `permissions` is `contents: read`, and the steps are `uv sync --locked` followed by `uv run` of `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `mypy tests/` and `pytest -q`.
- [ ] M3 (R6, T6, T10): read `LICENSE`, `.gitignore`, `.env.example` and the `[project]` table: MIT text with 2026 and your name, no email in authors, the tagline as description, `license = "MIT"` with `license-files = ["LICENSE"]`, `.gitignore` covering `.rkc/`, `.env`, virtual environments, caches and build artifacts, `.env.example` with empty placeholders only.
- [ ] M4 (R7, R8): read `CLAUDE.md` and `README.md`: the Specs section is intact, the commands match `specs/tech-stack.md`, the module map and the four rules are present, and the README does not claim functionality that does not exist.

## Understanding (cognitive debt)
- [ ] U1: read `cli.py` and the `--json` tests, and be able to explain why `--version` is plain text (Click processes eager options before others) while `rkc version` honors `--json` in either position, and where later commands will read the `--json` flag from.

## Definition of done
All boxes above are ticked, the deep review findings are resolved or consciously accepted, specs match the code, and the roadmap phase is marked complete.
