# LeanRAG baseline harness (phase 2 spike)

A throwaway harness that runs upstream LeanRAG ([KnowledgeXLab/LeanRAG](https://github.com/KnowledgeXLab/LeanRAG), by Yaoze Zhang et al., [arXiv:2508.10391](https://arxiv.org/abs/2508.10391)) **unmodified** to record the parity baseline for `rkc`'s own engine (phase 8). It is removed once that engine reaches parity. The spec is `specs/features/02-leanrag-baseline-spike/`.

Upstream has no LICENSE file, so none of its code or prompt text is copied into this repository. `setup.sh` clones it at a pinned commit into the gitignored `upstream/`, and the harness imports upstream's functions from there. The harness never edits a file in the clone.

## Layout

| Path | Committed | What |
|---|---|---|
| `setup.sh`, `teardown.sh` | yes | Environment setup and teardown |
| `docker-compose.yml`, `mysql-init/` | yes | MySQL for upstream |
| `harness/` | yes | Config writer, model adapter, `check` and the drivers |
| `tests/`, `pytest.ini` | yes | Harness tests (offline, run in the harness venv) |
| `upstream/` | no | Upstream clone at `ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3` |
| `work/` | no | Work directory: `venv/`, generated `config.yaml`, `tiktoken/` cache, downloaded datasets, Milvus Lite files, logs, raw build outputs before export |

## Prerequisites

- Linux with Docker and the Docker Compose plugin (`docker compose`).
- An NVIDIA GPU (the baseline used one RTX 4090, 24 GB) and [vLLM](https://docs.vllm.ai/) installed in its own environment.
- `git` and [uv](https://docs.astral.sh/uv/). `setup.sh` has uv fetch Python 3.12 if it is missing.

## Serving the models (one RTX 4090)

Two vLLM instances share the GPU, bound to localhost: the chat model on port 8001 with 80% of GPU memory, and the embedding model on port 8002 with 12%. Start the chat instance first and wait until it is ready.

Baseline chat model (Qwen3-30B-A3B-Instruct-2507, AWQ 4-bit, about 16.7 GB):

```sh
vllm serve stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ \
    --host 127.0.0.1 --port 8001 \
    --gpu-memory-utilization 0.80 \
    --max-model-len 32768 --kv-cache-dtype fp8
```

Development chat model, used only while developing the harness (never for the baseline):

```sh
vllm serve Qwen/Qwen3-4B-Instruct-2507 \
    --host 127.0.0.1 --port 8001 \
    --gpu-memory-utilization 0.80 \
    --max-model-len 32768 --kv-cache-dtype fp8
```

Embedding model (Qwen3-Embedding-0.6B, 1024 dimensions, which upstream hard-codes):

```sh
vllm serve Qwen/Qwen3-Embedding-0.6B --runner pooling \
    --host 127.0.0.1 --port 8002 \
    --gpu-memory-utilization 0.12 \
    --max-model-len 8192
```

The embedding instance's 8,192-token context keeps its memory share small. Upstream truncates the entity descriptions it embeds to 4,096 `cl100k_base` tokens. A longer embedding input fails loudly, because upstream's embedding call raises rather than returning an empty result.

**16k fallback.** If the development run shows that the 32k context with the fp8 KV cache does not fit next to the embedding instance, restart the chat instance with `--max-model-len 16384` instead of `32768`. Record this in the fixture README. Requests that then exceed the limit are findings: upstream truncates prompts only at 31,000 tokens, and it turns vLLM's rejection into a silent empty response, which the adapter counts.

The fixture README (`tests/fixtures/leanrag_baseline/README.md`) records the exact model revisions, the vLLM version and the command lines actually used.

## Environment variables

Endpoints and model names come only from these variables. No key is needed or read: vLLM runs without `--api-key`, so the generated `config.yaml` carries a fixed, non-secret placeholder.

```sh
export LEANRAG_CHAT_URL=http://127.0.0.1:8001/v1    # must be http(s)://host:port/v1
export LEANRAG_CHAT_MODEL=stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ
export LEANRAG_EMBED_URL=http://127.0.0.1:8002/v1
export LEANRAG_EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B
export LEANRAG_SEED=42                               # one fixed seed for every chat call
```

The model names must match what vLLM serves: by default, the repository name given to `vllm serve`.

Every chat call goes through upstream's own `InstanceManager` with `temperature=0` and `LEANRAG_SEED` added (upstream itself sends `enable_thinking: False`). The adapter also counts empty responses and records the longest prompt.

## Tests

The harness's tests run in the harness venv with their own `pytest.ini`, offline. `setup.sh` prefetches the tiktoken encoding they need.

```sh
cd scripts/spikes/leanrag && TIKTOKEN_CACHE_DIR=work/tiktoken work/venv/bin/pytest -q
```

They are not collected by the repository's `pytest` run or type-checked by `mypy`. `ruff check .` and `ruff format --check .` at the repository root do cover them.

## Run order

All commands run from `scripts/spikes/leanrag/` with the variables above exported. The harness's commands run as `work/venv/bin/python -m harness <command>`. They write upstream's `config.yaml` into `work/` and run upstream from there.

1. **Setup**: `./setup.sh`. Clones upstream at the pinned commit and verifies `HEAD`, creates the Python 3.12 venv with upstream's `requirements.txt` exactly plus `pytest`, and prefetches tiktoken's `cl100k_base`. A second run verifies instead of re-cloning.
2. **MySQL**: `docker compose up -d --wait`. This starts `mysql:8.4.13` on `127.0.0.1:4321` with upstream's fixed `root`/`123`, and root uses `mysql_native_password`.
3. **Models**: start both `vllm serve` instances (above).
4. **Check**: `work/venv/bin/python -m harness check`. Verifies the upstream commit and a clean working tree, a PyMySQL login with upstream's credentials, the chat model answering, 1024-length embeddings and both `/metrics` endpoints. It names whatever is wrong.
5. **Generate** the synthetic corpus with the baseline chat model: `work/venv/bin/python -m harness generate --model-revision <commit>`, where `<commit>` is the Hugging Face commit of the served chat model. It reads `tests/fixtures/leanrag_baseline/corpus_spec.yaml`, asks the model for each section's prose (canary payloads are never shown to it), inserts every planted item verbatim as its own paragraph, NFKC- and whitespace-normalises the text, and writes `articles/synthetic-NN.txt` and `articles.jsonl` (with `generated_by` and each planted item's character offsets) into the fixture directory. An article whose prose repeats a planted string fails and is not written; regenerate it with a temperature above 0 and another seed (at temperature 0 a new seed alone reproduces the same prose): `LEANRAG_SEED=<other> work/venv/bin/python -m harness generate --model-revision <commit> --only synthetic:NN --retry-temperature 0.7`. `--retry-temperature` is refused without `--only`; every other call stays at temperature 0. `generated_by` records the model, revision, seed and temperature per article (0 normally). Articles outside 2,500-3,500 words are reported as warnings. `--out work/dev-corpus` writes elsewhere, for development runs.
6. **Chunk** the synthetic corpus with upstream's chunker and write the offset map.
7. **Synthetic builds ×3**: three full builds (extraction, duplicate-entity merge, hierarchical clustering) with identical models, parameters and seed.
8. **Queries**: run the approved questions against each build, and run the context-string comparison with upstream's `query_graph` once.
9. **Measurement**: per-build metrics, the FTS5 baseline and `tolerance.json`.
10. **`mix` download**: fetch UltraDomain `mix.jsonl` at the pinned revision into `work/` and verify its SHA-256.
11. **`mix` chunk and build**: chunk as upstream's `file_chunk.py` does, compare the chunk hashes with upstream's shipped `mix_chunk.json`, then one build.
12. **`mix` queries and judge**: the 130 questions, then the pairwise judge against upstream's published answers.
13. **Teardown**: `./teardown.sh`. Stops MySQL and removes its data volume. Afterwards `docker volume ls` shows no `leanrag-spike` volume. To remove the harness's local state too, delete `upstream/` and `work/`.

Steps 6 to 12 are harness commands added by the later groups of the phase 2 plan.
