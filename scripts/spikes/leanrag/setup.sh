#!/usr/bin/env bash
# Set up the LeanRAG baseline harness (phase 2).
#
# - Clones upstream LeanRAG into the gitignored ./upstream, checks out the pinned
#   commit and verifies HEAD. A second run verifies instead of re-cloning.
# - Creates the harness venv (Python 3.12, uv) in ./work/venv and installs
#   upstream's requirements.txt exactly, plus pytest.
# - Prefetches tiktoken's cl100k_base into ./work/tiktoken (TIKTOKEN_CACHE_DIR),
#   so tests and later runs need no network for it.
#
# Usage: scripts/spikes/leanrag/setup.sh
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")" && pwd)"
UPSTREAM_URL="https://github.com/KnowledgeXLab/LeanRAG.git"
UPSTREAM_COMMIT="ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3"
UPSTREAM_DIR="$HARNESS_DIR/upstream"
WORK_DIR="$HARNESS_DIR/work"
VENV_DIR="$WORK_DIR/venv"
TIKTOKEN_DIR="$WORK_DIR/tiktoken"
PYTHON_VERSION="3.12"
PYTEST_PIN="pytest==9.2.0"

say() { echo "==> $*"; }
die() { echo "setup: $*" >&2; exit 1; }

command -v git >/dev/null || die "git is not installed"
command -v uv >/dev/null || die "uv is not installed (https://docs.astral.sh/uv/)"

# 1. Upstream clone at the pinned commit.
if [[ -d "$UPSTREAM_DIR/.git" ]]; then
    say "Upstream clone exists; verifying"
else
    [[ -e "$UPSTREAM_DIR" ]] && die "$UPSTREAM_DIR exists but is not a git clone; remove it and rerun"
    say "Cloning $UPSTREAM_URL"
    git clone --quiet "$UPSTREAM_URL" "$UPSTREAM_DIR"
    git -C "$UPSTREAM_DIR" -c advice.detachedHead=false checkout --quiet "$UPSTREAM_COMMIT"
fi
head="$(git -C "$UPSTREAM_DIR" rev-parse HEAD)"
[[ "$head" == "$UPSTREAM_COMMIT" ]] \
    || die "upstream HEAD is $head, expected $UPSTREAM_COMMIT (the clone is never changed by the harness; remove $UPSTREAM_DIR and rerun)"
[[ -z "$(git -C "$UPSTREAM_DIR" status --porcelain)" ]] \
    || die "upstream working tree has changes; upstream must run unmodified (git -C $UPSTREAM_DIR status)"
say "Upstream at $UPSTREAM_COMMIT, working tree clean"

# 2. Harness venv: Python 3.12, upstream's pins unchanged, plus pytest.
mkdir -p "$WORK_DIR"
if [[ -x "$VENV_DIR/bin/python" ]]; then
    say "Harness venv exists; verifying"
else
    say "Creating harness venv (Python $PYTHON_VERSION)"
    uv venv --quiet --python "$PYTHON_VERSION" "$VENV_DIR"
fi
venv_version="$("$VENV_DIR/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
[[ "$venv_version" == "$PYTHON_VERSION" ]] \
    || die "harness venv runs Python $venv_version, expected $PYTHON_VERSION; remove $VENV_DIR and rerun"
say "Installing upstream requirements.txt and $PYTEST_PIN"
uv pip install --quiet --python "$VENV_DIR/bin/python" \
    -r "$UPSTREAM_DIR/requirements.txt" "$PYTEST_PIN"

# 3. tiktoken encoding, cached inside the work directory.
say "Prefetching tiktoken cl100k_base into $TIKTOKEN_DIR"
mkdir -p "$TIKTOKEN_DIR"
TIKTOKEN_CACHE_DIR="$TIKTOKEN_DIR" "$VENV_DIR/bin/python" -I -c \
    'import tiktoken; tiktoken.get_encoding("cl100k_base")'

say "Setup complete. Next: start MySQL and vLLM (see README.md), then run check."
