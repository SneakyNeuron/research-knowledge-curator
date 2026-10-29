# Phase 01: Scaffolding — Requirements

## Functional
- R1: `rkc --version` prints `rkc <version>` on stdout and exits 0, where `<version>` is the package version from `pyproject.toml`. It is plain text and ignores `--json`.
- R2: `rkc version` prints `rkc <version>`. With `--json`, given either before the subcommand (`rkc --json version`) or after it (`rkc version --json`), it prints exactly one JSON object `{"version": "<version>"}` on stdout. Exit 0, and stderr stays empty.
- R3: `rkc --help` lists only implemented commands and options: in this phase the `version` command and the options `--version`, `--json` and `--help`, with no shell-completion options.
- R4: Bare `rkc` (with or without `--json`) is a usage error: it prints the help text to stdout and exits 2, following Click 8.2+ and `uv`.
- R5: `research-knowledge-curator` is an equivalent command: both console scripts point to the same entry point.
- R6: The repository has an MIT `LICENSE`, a `.gitignore` covering `.rkc/`, `.env`, virtual environments, caches and build artifacts, and an `.env.example` with placeholder variable names only.
- R7: `CLAUDE.md` gives a coding agent the commands, the module map, and the untrusted-data, store-owns-the-facts, scan-every-hop and secrets rules, while keeping the existing Specs section.
- R8: `README.md` states the honest status, the user install command and the developer commands.

## Technical
- T1: `requires-python = ">=3.12"`. `.python-version` stays `3.14`. The build backend stays `uv_build`, bumped to its current release range (`>=0.13.6,<0.14` at spec time).
- T2: The only runtime dependency is `typer`, pinned to its current PyPI release (checked at implementation). Dev tools `pytest`, `pytest-socket`, `ruff` and `mypy` are pinned to their current releases in a `dev` dependency group. `uv.lock` is committed.
- T3: The version has a single source, `[project] version`, read at runtime through `importlib.metadata`. No hard-coded version string in `src/`.
- T4: Ruff: `target-version = "py312"`, `line-length = 100`, `select = ["E", "W", "F", "I", "B", "UP", "SIM", "RUF", "S", "PTH"]`, with `S101` ignored under `tests/`. Format is checked with `ruff format --check`.
- T5: `uv run mypy --strict src/` and `uv run mypy tests/` (default settings) both pass. Strictness is not configured globally in a way that applies `--strict` to tests.
- T6: Package metadata: description is the tagline "Agent-maintained, evidence-anchored research knowledge base"; authors list the name "Vojtěch Kubín" only, with no email; `license = "MIT"` (SPDX expression) with `license-files = ["LICENSE"]`.
- T7: Tests are offline and need no keys or Docker. `pytest-socket` with `--disable-socket` in the pytest configuration makes any network access fail the suite, locally and in CI. Tests use Typer's `CliRunner` plus `tomllib`.
- T8: CI (`.github/workflows/ci.yml`) runs on every push and pull request, on Python 3.12 and 3.14, passing the matrix version through `astral-sh/setup-uv`'s `python-version` input, with `permissions: contents: read`, every action pinned to a full commit SHA (version tag in a comment), `persist-credentials: false` on checkout, `uv sync --locked`, and the same five commands as local: `ruff check .`, `ruff format --check .`, `mypy --strict src/`, `mypy tests/`, `pytest -q`.
- T9: Data goes to stdout and messages to stderr. The JSON helper writes one plain `json.dumps` object per invocation to stdout (no rich console, colour or wrapping); help, usage errors and diagnostics never enter stdout's JSON stream.
- T10: `.env.example` contains no values, only empty `NAME=` lines and comments.

## Out of scope
- Any runtime dependency other than `typer`; every later library is added and pinned by the phase that first uses it.
- Any subcommand other than `version` (`init`, `doctor`, ...) and any module other than `cli.py` and `__init__.py`.
- PyPI classifiers, keywords, project URLs and publishing (phase 14).
- The `.rkc/<cluster>/` gitignore rules for host projects, where configuration files are tracked (phase 2's `rkc init`). This repository's own `.gitignore` ignores `.rkc/` entirely.
- A `uv build` / `uv tool install` wheel check (phase 14 owns the release check).
- Running `actionlint` or `zizmor` in CI (local checks only in this phase).
- Creating the GitHub repository (it already exists) and pushing (the owner does that).

## Decisions
| Decision | Choice | Reason | Decided in |
|---|---|---|---|
| Runtime dependencies in phase 1 | `typer` only | Constitution: pin each dependency when it is introduced; overrides design Step 1's full list | spec interview |
| Ruff strictness | Curated set E, W, F, I, B, UP, SIM, RUF, S, PTH; S101 allowed in tests; line length 100 | Catches real bugs and security smells (bandit) without `ALL`'s churn | spec interview |
| CI action pinning | Full commit SHA with version comment, read-only permissions, `persist-credentials: false` | Supply-chain safety fits the security-first mission; OpenSSF Scorecard and zizmor guidance | spec interview; credentials added in spec review |
| `--json` effect in phase 1 | Originally: `--json` switched `--version` to JSON. Changed: `--version` stays plain; `rkc version` subcommand honors `--json` in either position | Eager `--version` runs before `--json` is parsed; a `version` subcommand is the convention (`kubectl`, `docker`, `uv`) | spec interview; changed in spec review |
| Bare `rkc` | Help text, exit 2 (was exit 0) | Click 8.2+ and `uv` treat it as a usage error; 2 is the Unix usage-error code | spec interview; changed in spec review |
| CI Python selection | setup-uv `python-version` input from the matrix | uv's documented GitHub Actions pattern; otherwise `.python-version` makes the 3.12 job run on 3.14 | spec review |
| Offline tests | `pytest-socket` with `--disable-socket` | Standard plugin; enforces the offline policy in every run instead of one manual check | spec review |
| Version test oracle | Compare with `[project] version` read by `tomllib` | Tests R1 against its source, not against the code's own lookup | spec review |
| Author metadata | Name only, no email | Owner's choice for public PyPI metadata | spec interview |
| `.env.example` content | Explanatory header plus empty `OPENALEX_API_KEY=` and `OPENAI_API_KEY=` | Shows the `api_key_env` pattern without fixing names phase 2 owns | spec interview |
| Extra scope | README developer section and real `pyproject` description; no classifiers or URLs | Small, useful now; release metadata belongs to phase 14 | spec interview |
| Version source | `pyproject.toml` via `importlib.metadata` | One source of truth; packaging guide recommendation | spec interview |
| Shell completion options | Disabled | Agent-facing CLI; `--help` must list only implemented options | spec interview |
| Version string format | `rkc <version>` from both console scripts | The two commands are equivalent | spec interview |
| Default branch and remote | `main`, `origin = git@github.com:SneakyNeuron/research-knowledge-curator.git`, public | GitHub default; owner connected the repo during the interview | spec interview |
| Bare `rkc` mechanism | `invoke_without_command=True`; callback prints help and exits 2 | `no_args_is_help` does not cover `rkc --json` (verified in due diligence) | due diligence |
| zizmor mode | Offline (`--offline`) | Covers pinning, permissions and credentials without a GitHub token | due diligence |
| `uv_build` version | Bump to `>=0.13.6,<0.14` | Constitution: pin current releases; local uv 0.12.8 still fetches it | due diligence |
| CI proof before push | actionlint, zizmor and a local Python 3.12 test run, then CI green after the owner pushes | No push from the agent; still proves 3.12 support and workflow syntax and security | spec interview; zizmor added in spec review |
