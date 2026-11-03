# Phase 02: LeanRAG baseline spike — Validation

Harness test command (T7): `cd scripts/spikes/leanrag && TIKTOKEN_CACHE_DIR=<work>/tiktoken <venv>/bin/pytest -q`.

## Automated
- [ ] V1 (T7, T8): `scripts/check.sh` passes: ruff check and format over the repo (harness included), both mypy runs, and `pytest` plain and under CI's colour variables.
- [ ] V2 (R3, R4, R6, T8, T10, T11): `uv run pytest -q tests/test_leanrag_baseline_fixture.py` passes. It checks that:
  - every article is `synthetic: true` with a text file;
  - every planted offset slices to its string, and that string occurs exactly once in its article;
  - the planted items meet R4's counts by `kind`;
  - every article text is unchanged by NFKC normalisation;
  - every `chunk_map` span matches its chunk after upstream's post-processing and the `split_char` edge rule, and every chunk is mapped;
  - only allowed file types are present.
- [ ] V3 (T2, T3, T9): the harness tests for the model adapter and config writer pass (temperature, seed and `enable_thinking` sent on every call through a fake transport, empty responses counted, longest prompt recorded, exactly five config keys, no secret).
- [ ] V4 (R4, T10): the harness tests for the generator pass (verbatim insertion at paragraph boundaries, exact offsets, idempotent normalisation, duplicate planted string rejected, canaries intact).
- [ ] V5 (R6): the harness tests for the offset mapper pass (ASCII, multi-byte characters at boundaries with the flagged-window comparison, overlap, short final window, short article, duplicate chunk text, mismatch fails loudly).
- [ ] V6 (R9, R10, T13, T14): the harness tests for the build helpers, measurements and judge pass. They cover:
  - build helpers: the build-name check, the SQL-error scanner, the `/metrics` delta parser;
  - measurements: Jaccard and overlap, span recall, case-insensitive canary inside-versus-spread, metacharacter comparison after normalisation, the FTS5 query builder and toy corpus, `tolerance.json` and the parity rule;
  - `mix`: hash refusal, stable question keys, judge parsing and two-order win rates.
- [ ] V7 (R2): after all runs, `git -C <upstream clone> status --porcelain` is empty and `git -C <upstream clone> rev-parse HEAD` prints `ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3`.
- [ ] V8 (R2, R8): `--compare-query-graph` reports an identical context string for its question.
- [ ] V9 (T5): `docker compose config` for the harness shows image `mysql:8.4.13`, published only on `127.0.0.1:4321`, with native-password authentication enabled.
- [ ] V10 (R2, T3, T6, T11): checks on the committed files:
  - `git ls-files` lists no PDF, Milvus or `.db` file, no generated `config.yaml`, no `mix.jsonl`, and nothing under the upstream clone or the work directory;
  - `du -sh tests/fixtures/leanrag_baseline` is under 25 MB;
  - `git grep` finds no key value from the environment the owner used;
  - for a sample of 10 distinctive lines from upstream's `prompt.py` and `evaluate_score.py`, `git grep -F` finds none in the repository outside `specs/`.
- [ ] V11 (T4): `git diff main -- pyproject.toml uv.lock` shows only the `S101` per-file ignore for the harness's tests.
- [ ] V12 (R7, R9): `tests/fixtures/leanrag_baseline/builds/synthetic-1`, `synthetic-2` and `synthetic-3` each contain:
  - the extraction outputs and the MySQL table exports;
  - query results for every approved question;
  - `metrics.json` and the cost log.

  `tolerance.json` has per-build outcome values with min, mean and max, the informational overlaps, and the proposed parity rule.
- [ ] V13 (R10): `tests/fixtures/leanrag_baseline/mix/` contains:
  - the chunk-hash comparison result;
  - per-question records for all 130 questions (key, entity names, text-unit hashes, answer);
  - judge verdicts in both orders with win rates;
  - the cost log, hierarchy shape and `metrics.json`.

  No record contains a `context` field or `mix` source text.

## Manual (human in the loop)
- [ ] M1 (R1, T1, T5): on the RTX 4090, follow `scripts/spikes/leanrag/README.md` from a clean checkout. Then:
  - setup, the two `vllm serve` commands and `check` succeed;
  - `check` reports the upstream commit, the MySQL login, the chat model, a 1024-length embedding and both `/metrics` endpoints;
  - after teardown, `docker volume ls` shows no harness volume.
- [ ] M2 (R3, R4): read 3 articles, including one canary article and one with a metacharacter name. The prose is coherent finance-evaluation text, planted facts read naturally, and nothing is copied from a real paper you recognise.
- [ ] M3 (R5): review `questions.yaml`, edit it as needed and set it to `approved` (with the date) before the first baseline build. Confirm it has 15–20 questions, the 3 `fin-model-evaluation` questions from `docs/topics.md` as `seed`, at least 2 `negative` questions, and at least one question for every disagreement pair in `corpus_spec.yaml`.
- [ ] M4 (R7, R10, T2, T9): run the three synthetic builds, the `mix` build and their query drivers. Each build log shows:
  - per-stage requests, tokens from both instances, wall time and the longest prompt;
  - zero empty responses, or an accepted, documented count.

  The dev run's result on fitting 32k is recorded.
- [ ] M5 (T1, T12): the fixture README names:
  - the exact model repos and revisions, and the quantisation;
  - the vLLM version and both `serve` command lines (context length and KV dtype as used);
  - GPU and driver, MySQL image tag, harness Python version and seed;
  - the UltraDomain revision and hash.

  It also labels the model-written files as generated.
- [ ] M6 (R12, R13): read `docs/spikes/leanrag.md`. Check that:
  - every section listed in R12 is present;
  - cost is extrapolated to 100 and 1,000 articles;
  - the per-question table matches `metrics.json`;
  - implications for the reimplementation are concrete;
  - no upstream code or prompt text is quoted;
  - the decision says phase 8 proceeds with the approved parity rule.
- [ ] M7 (R9): pick one canary article and trace its token through the synthetic build exports. Confirm the doc's inside-versus-spread classification for it is right.
- [ ] M8 (R10): read the `mix` chunk-hash comparison and judge results. If the hashes match upstream's `mix_chunk.json` and the win rate against upstream's published answers is near 50%, the harness drives upstream faithfully. Otherwise confirm the doc explains the difference (for example, different models from upstream's).
- [ ] M9 (R11): review the proposed parity rule and its numbers in `tolerance.json`, adjust them if needed, and mark the rule approved with the date.
- [ ] M10 (R14): read `specs/roadmap.md` phases 2 and 8 and `specs/tech-stack.md`'s project structure. Confirm they describe this spec (synthetic corpus and `mix`, three plus one builds, fixture location, decision moved to phase 8).

## Understanding (cognitive debt)
- [ ] U1: read the offset mapper and its tests. Be able to explain why upstream's chunk text cannot be located by string search in the article (newlines removed, overlap, duplicate hashes, split characters) and how the map recovers spans.
- [ ] U2: read how `tolerance.json` and the parity rule are computed. Be able to explain what phase 8's engine has to show to pass on each benchmark, and why the rule uses outcomes rather than chunk overlap.

## Definition of done
All boxes above are ticked, the deep review findings are resolved or consciously accepted, specs match the code, and the roadmap phase is marked complete.
