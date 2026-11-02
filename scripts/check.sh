#!/usr/bin/env bash
# Run every quality gate, including the test runs under CI's colour variables.
# Stops at the first failure. Usage: scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

run() {
    echo "==> $*"
    "$@"
}

run uv run ruff check .
run uv run ruff format --check .
run uv run mypy --strict src/
run uv run mypy tests/
run uv run pytest -q
# Typer forces colour (ANSI codes) when these are set, as on GitHub Actions.
for var in GITHUB_ACTIONS=true FORCE_COLOR=1 PY_COLORS=1; do
    run env "$var" uv run pytest -q
done
echo "==> All checks passed"
