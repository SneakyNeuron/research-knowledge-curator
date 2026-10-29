# Phase 01: Scaffolding — Plan

## Context
Roadmap phase 1. The repository holds only the constitution and a `uv init` scaffold (`requires-python >=3.14`, a hello-world `main`, no tests, no tooling). Every later phase assumes a packaged `rkc` command, the four quality gates from `specs/tech-stack.md`, and CI on every supported Python version. This phase puts that foundation in place and nothing more.

## Approach
- Add only what this phase uses. The archived design (Step 1) lists all runtime dependencies up front, but the constitution says each dependency is pinned when it is introduced, so the only runtime dependency is `typer`. Dev tools (`pytest`, `pytest-socket`, `ruff`, `mypy`) go in a `dev` dependency group.
- Follow current CLI conventions (Click's `version_option`, clig.dev, and tools such as `kubectl`, `docker` and `uv`): `--version` prints plain text, and machine-readable version info comes from a `version` subcommand that honors `--json`. Data goes to stdout, messages to stderr. A bare invocation is a usage error: help text and exit code 2, as Click 8.2+ and `uv` do.
- The version has one source: `version` in `pyproject.toml`, read at runtime with `importlib.metadata` (the Python packaging guide's recommendation).
- `cli.py` holds the Typer app and a small JSON output helper (plain `json.dumps` to stdout, never a rich console) that later commands reuse. Both console scripts point at the same object, so `rkc` and `research-knowledge-curator` are equivalent by construction.
- `--json` works both before a subcommand (`rkc --json version`) and after it (`rkc version --json`), so agents can put it either place.
- Tests are offline by construction: `pytest-socket` blocks network access for the whole suite.
- CI mirrors the local gates exactly, on Python 3.12 and 3.14. The matrix version reaches uv through `astral-sh/setup-uv`'s `python-version` input, as uv's GitHub Actions guide documents, so `.python-version` (3.14) does not override it. Actions are pinned by commit SHA, permissions are read-only, and checkout does not keep credentials, following OpenSSF Scorecard and `zizmor` guidance.
- The GitHub remote (`git@github.com:SneakyNeuron/research-knowledge-curator.git`) and the `main` default branch were set up during the spec interview. The owner pushes; the agent does not.

## What stays unchanged
- `specs/` other than this feature directory and the roadmap's `Spec:` line (and the roadmap phase checkbox at validation).
- `docs/topics.md` and the archived design in `specs/backlog/`.
- `.python-version` stays at `3.14` (the development version).
- No runtime dependency other than `typer`; no module other than `cli.py` and `__init__.py`.

## Group 1: Package and `--version`
- [ ] `pyproject.toml`: `requires-python = ">=3.12"`, description set to the tagline, author as name only (no email), `license = "MIT"` with `license-files = ["LICENSE"]`, `typer` pinned to its current release, console scripts `rkc` and `research-knowledge-curator` both pointing to the CLI entry point in `research_knowledge_curator.cli`, and a `dev` dependency group with `pytest`, `pytest-socket`, `ruff` and `mypy` pinned to their current releases.
- [ ] Tool configuration in `pyproject.toml`: ruff (target `py312`, line length 100, the rule set in T4), pytest (`testpaths = ["tests"]`, `--strict-markers`, `--disable-socket`), mypy settings that do not force strict on tests (strictness for `src/` comes from the `--strict` flag).
- [ ] Bump the build backend to the current `uv_build` release range (`uv_build>=0.13.6,<0.14` at spec time; re-check at implementation).
- [ ] `LICENSE` (MIT, 2026, Vojtěch Kubín).
- [ ] Remove the hello-world `main` from `__init__.py`.
- [ ] `cli.py`: Typer app with an eager `--version` option (`typer.Option(is_eager=True)` with a callback; Typer 0.26+ vendors Click, so `click` is not importable) that prints `rkc <version>` and exits 0. Shell completion options disabled.
- [ ] `uv lock` and commit `uv.lock`.
- [ ] Tests (written first, `tests/test_cli_smoke.py`): `--version` stdout and exit code; the printed version equals `[project] version` read from `pyproject.toml` with `tomllib`; both console scripts in `pyproject.toml` resolve to the same target; a test that opening a socket fails (proves `pytest-socket` is active).

## Group 2: `version` subcommand, global `--json`, help and bare invocation
- [ ] JSON output helper in `cli.py`: writes one object as a single line of plain `json.dumps` output to stdout. Used by every command that honors `--json`.
- [ ] `--json` accepted globally on the app callback and on the `version` command, with the same effect either way; later commands reuse the same mechanism.
- [ ] `rkc version` prints `rkc <version>`; `rkc version --json` and `rkc --json version` print `{"version": "<version>"}`. Exit 0.
- [ ] Bare `rkc` (and `rkc --json` with no command) prints the help text to stdout and exits 2. Method: `typer.Typer(add_completion=False, invoke_without_command=True)`, and the app callback, when `ctx.invoked_subcommand is None`, echoes `ctx.get_help()` and raises `typer.Exit(2)`. Do not use `no_args_is_help`, which misses `rkc --json`.
- [ ] `--help` shows `--version`, `--json`, `--help` and the `version` command only; no completion options.
- [ ] Tests (written first), asserting on `result.stdout` and `result.stderr` separately: both `--json` positions parse with `json.loads` to `{"version": ...}` with empty stderr; plain `rkc version` is not JSON; bare invocation and `rkc --json` show help and exit 2; help lists exactly the `version` command and no completion options; `rkc --bogus` puts a usage error on stderr, nothing on stdout, non-zero exit.

## Group 3: Repository hygiene and docs
- [ ] `.gitignore`: keep the existing entries and add build artifacts (`build/`, `*.egg-info/`).
- [ ] `.env.example`: a header explaining that secrets live only in the environment or `.env`, that agent and cluster YAML refer to keys by variable name through `api_key_env`, and that the file must never hold real values; empty placeholders `OPENALEX_API_KEY=` and an example model key `OPENAI_API_KEY=`.
- [ ] `CLAUDE.md`: keep the existing Specs section; add the commands (`uv sync`, the four gates plus `mypy tests/`), the module map from `specs/tech-stack.md` (marking which modules exist), and the rules: everything fetched or model-written is untrusted data and never builds paths, URLs, SQL or commands; the store owns the facts; scan at every hop; secrets never in YAML, store, logs or output.
- [ ] `README.md`: keep the status honest (scaffolding, nothing functional yet); add user install (`uv tool install research-knowledge-curator`, noting it is not yet on PyPI) and the developer commands.
- [ ] Tests: none new (documentation and configuration only); the existing suite and gates still pass.

## Group 4: CI workflow
- [ ] `.github/workflows/ci.yml`: triggers on `push` and `pull_request`; `permissions: contents: read`; matrix Python 3.12 and 3.14; `actions/checkout` (with `persist-credentials: false`) and `astral-sh/setup-uv` (with `python-version: ${{ matrix.python-version }}`) pinned to full commit SHAs of their current releases, with the version tag in a trailing comment; a step that prints the Python version in use; `uv sync --locked`; then `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `mypy tests/` and `pytest -q`, each through `uv run`.
- [ ] Run `uvx --from actionlint-py actionlint .github/workflows/ci.yml` and `uvx zizmor --offline .github/workflows/ci.yml` locally (ad hoc, not added as dependencies) and fix anything they report.
- [ ] Run the test suite on Python 3.12 locally in an isolated environment, so the development `.venv` stays on 3.14.
- [ ] Tests: none new; actionlint, zizmor and the 3.12 run are the checks for this group.

## Edge cases
- `rkc --version --json` → plain `rkc <version>` (eager `--version` ignores `--json`; JSON version info is `rkc version --json`).
- `rkc --json` alone → same as bare `rkc`: help text, exit 2 (help is never JSON).
- `rkc --bogus` → Typer usage error on stderr, non-zero exit, nothing on stdout.
- Package not installed (running from a source tree without `uv sync`) → not supported; tests run through `uv run`, which installs the project.
- `research-knowledge-curator --version` → prints `rkc <version>`, identical to `rkc --version`.
