#!/usr/bin/env bash
# Stop the harness's MySQL container and remove its data volume.
# The upstream clone and the work directory are left in place; delete them by hand
# (rm -rf upstream work) to remove the harness entirely.
# Usage: scripts/spikes/leanrag/teardown.sh
set -euo pipefail
cd "$(dirname "$0")"
docker compose down --volumes --remove-orphans
