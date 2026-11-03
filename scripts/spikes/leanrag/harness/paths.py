"""Fixed locations and the upstream pin, plus how drivers import upstream.

Upstream reads ``config.yaml`` from the working directory and imports its own
modules as top-level names, so drivers run with the work directory as the
working directory and two upstream directories on ``sys.path``: the clone's root
(``prompt``, ``tools``, ``database_utils``) and ``GraphExtraction/`` (whose
``chunk.py`` imports ``_utils`` as a top-level module).
"""

import os
import sys
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent.parent
UPSTREAM_DIR = HARNESS_DIR / "upstream"
WORK_DIR = HARNESS_DIR / "work"
VENV_DIR = WORK_DIR / "venv"
TIKTOKEN_DIR = WORK_DIR / "tiktoken"

UPSTREAM_URL = "https://github.com/KnowledgeXLab/LeanRAG.git"
UPSTREAM_COMMIT = "ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3"

# Upstream's hard-coded MySQL server and credentials (accepted for a
# localhost-only, throwaway container; see the spec, T5).
MYSQL_HOST = "localhost"
MYSQL_PORT = 4321
MYSQL_USER = "root"
MYSQL_PASSWORD = "123"  # noqa: S105 - upstream's fixed throwaway credential, not a secret

# Upstream hard-codes a vector dimension of 1024.
EMBEDDING_DIM = 1024


def make_upstream_importable() -> None:
    """Put upstream on ``sys.path`` and point tiktoken at the prefetched cache.

    Idempotent. Upstream modules call ``tiktoken.get_encoding`` at import time,
    so the cache directory must be set before the first upstream import.
    """
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(TIKTOKEN_DIR))
    for directory in (UPSTREAM_DIR / "GraphExtraction", UPSTREAM_DIR):
        entry = str(directory)
        if entry not in sys.path:
            sys.path.insert(0, entry)


def enter_work_dir() -> None:
    """Make the work directory the working directory, as upstream expects."""
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    os.chdir(WORK_DIR)
