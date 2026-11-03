# Phase 02: LeanRAG baseline spike — Plan

## Context
Roadmap phase 2. Phase 8 builds `rkc`'s hierarchical retrieval engine. Its go/no-go is parity: it must reproduce what upstream LeanRAG (KnowledgeXLab/LeanRAG) does. This phase produces what parity is measured against. It also records the findings that shape the engine (traceability, cost, injection behaviour, SQL handling, disagreement survival). There are two benchmarks:
- **A synthetic corpus**, committed in full: about 40 articles with known answers, run through three upstream builds. Its run-to-run variance gives the tolerance band.
- **Upstream's own benchmark**, UltraDomain `mix`: 130 questions over book-length texts, downloaded at a pinned revision and not committed, run through one upstream build. It shows the engine reproduces LeanRAG on the data its paper reports.

**Licence finding (spec review, 2026-11-02).** Upstream has no LICENSE file anywhere in its history; the only MIT claim is a README badge that links to a missing file. The owner decided that phase 8 reimplements LeanRAG from its paper (arXiv 2508.10391) rather than vendoring the code, and credits the paper and repository in the README. The 2026-11-03 replan updated the constitution (mission, tech stack, `CLAUDE.md`, roadmap phases 8, 9 and 13) from vendoring to reimplementation. For this phase it means:
- upstream runs only from a local, gitignored clone;
- no upstream code or prompt text is copied into any committed file;
- the findings document describes upstream's behaviour in our own words, never by pasting its code or prompts.

Upstream at `ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3` (2026-07-07, still `HEAD` at spec time) is unpackaged research code:
- scripts with hard-coded paths in their `__main__` blocks, and a `config.yaml` read from the working directory;
- MySQL hard-coded to `localhost:4321` as `root`/`123`;
- vectors in Milvus Lite (a local file, no server) with a hard-coded dimension of 1024.

Its chunker (`file_chunk.chunk_documents`) keeps `{hash_code, text}` only, drops newlines from the text and records no offsets. Its query entry point (`query_graph.query_graph`) returns one formatted context string plus the model's answer. Its repository ships `datasets/` with the UltraDomain `mix` chunk file and LeanRAG's published answers, and a `dataset.sh` that downloads the UltraDomain source files from Hugging Face.

## Approach
- **Synthetic corpus, committed in full.** About 40 synthetic articles in the `fin-model-evaluation` domain. The local Qwen3-30B-A3B writes them from a committed spec, and a script inserts planted facts, disagreements, injection canaries and metacharacter-laden names verbatim. Most real papers' licenses do not allow redistribution, while a parity test needs its input in the repo. Synthetic input also gives ground truth: each question has known answer spans. The trade-off is realism (clean text, no PDF artefacts), recorded as a limitation; real papers are exercised in phase 13's end-to-end check.
- **UltraDomain `mix`, one build, not committed.** `mix.jsonl` is downloaded from `TommyChien/UltraDomain` (Apache-2.0 on Hugging Face) at a pinned revision and verified by hash, into the gitignored work directory. Upstream's chunker runs on it as its own `file_chunk.py` `__main__` does. The resulting chunk hashes are compared with the `mix_chunk.json` upstream ships, to check that the harness drives upstream faithfully. One build and the 130 questions follow. A pairwise LLM judge (our own prompt over the four criteria the paper names: comprehensiveness, diversity, empowerment and overall) compares our upstream run with upstream's published `mix` answers as a sanity check. Phase 8 later uses the same judge to compare its engine with this build. Only hashes, generated text and metrics are committed for `mix`.
- **Upstream runs unmodified.**
  - A throwaway harness in `scripts/spikes/leanrag/` clones the pinned commit into a gitignored directory and installs upstream's `requirements.txt` into its own `uv` venv.
  - Its driver scripts import and call upstream's functions with a generated `config.yaml`, replacing only the `__main__` blocks.
  - Model calls go through upstream's own `tools.utils.InstanceManager`, pointed at vLLM, with `temperature=0` and a fixed `seed` passed as request kwargs.
  - MySQL 8.4 runs in a Docker container bound to `127.0.0.1:4321` with upstream's fixed credentials and native-password authentication. Upstream's pinned PyMySQL cannot use MySQL's default authentication without the `cryptography` package, which upstream's pins do not include.
- **GraphExtraction path.** LLM few-shot entity and relation extraction (`GraphExtraction/chunk.py`, then `GraphExtraction/deal_triple.py`), then `build_graph.py`'s hierarchical clustering. CommonKG is not used.
- **Traceability added outside upstream.** The harness runs upstream's chunker unchanged (1024 tokens, overlap 128, `cl100k_base`) and builds a side map from each synthetic chunk back to its article and character offsets. Upstream behaviour is preserved, and the doc records exactly what the engine must add.
- **Structured queries.** For each question, the harness calls the same upstream functions `query_graph` calls, in the same order, to capture the pieces (entities, reasoning paths, aggregations, text units), then makes the same answer call. Pairwise comparison of the three synthetic builds gives the tolerance band.
- **Outcome-based parity.** A reimplementation writes its own prompts, so its chunk and entity sets will differ from upstream's even when it works as well. The proposed parity rule is therefore defined on outcomes:
  - Synthetic corpus: planted-fact recall, answer hits and disagreement retrieval are each at least the worst of the three upstream builds, and canary spread is at most the worst.
  - `mix`: the pairwise judge cannot tell the engine from upstream, with an overall win rate between 40% and 60% averaged over both answer orders.

  Chunk and entity overlap are recorded for information only. The owner approves the exact numbers at the end of this phase.
- **Models on one RTX 4090 through vLLM.**
  - Chat: `stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ` (16.7 GB, 4-bit), with `--max-model-len 32768` and `--kv-cache-dtype fp8`. That covers upstream's 31,000-token prompt truncation in about 1.5 GiB of KV cache.
  - Embedding: Qwen3-Embedding-0.6B (1024 dimensions), served with `--runner pooling`.
  - The two run as two vLLM instances sharing the GPU.
  - Qwen3-4B-Instruct-2507 is used only while developing the harness.
  - If the dev run shows 32k does not fit, the owner falls back to 16,384 and over-length requests are recorded as findings.
- **The decision moves to phase 8.** Phase 2 is done when both baselines and the tolerance band are recorded. Phase 8 decides what happens if its engine cannot reach parity. Traceability, cost and injection results are findings, not gates.

## What stays unchanged
- `src/`, the CLI and `pyproject.toml`'s dependencies. `rkc` gains no runtime or dev dependency. The only `pyproject.toml` change allowed is a ruff per-file ignore for the harness's tests.
- The CI workflow. The harness's own tests do not run in CI. The main suite's new fixture-integrity test does, since it is part of `pytest`.
- `specs/mission.md`, `docs/topics.md`, and the archived design.
- The cloned upstream code: no file in it is edited. No upstream code or prompt text is copied into a committed file.

## Group 1: Harness skeleton, environment and model adapter
- [x] `.gitignore`: ignore the upstream clone and the harness's work directory (venv, generated `config.yaml`, tiktoken cache, downloaded datasets, Milvus Lite files, logs, raw build outputs before export), both under `scripts/spikes/leanrag/`.
- [x] Setup script:
  - Clones upstream into the gitignored directory, checks out `ee2d524cf6e216712122bdbc1fecd0d5b3eec7d3` and verifies `HEAD`.
  - Creates the harness venv with `uv` on Python 3.12 and installs upstream's `requirements.txt` exactly, plus `pytest`.
  - Prefetches tiktoken's `cl100k_base` into a `TIKTOKEN_CACHE_DIR` inside the work directory, so tests and later runs need no network for it.
  - Is idempotent: a second run verifies rather than re-clones.
- [x] `docker-compose.yml` for MySQL:
  - image `mysql:8.4.13` (exact tag), published only on `127.0.0.1:4321`;
  - upstream's fixed credentials;
  - `root` authenticating with `mysql_native_password` (the server's `--mysql-native-password=ON` plus whatever init step or authentication policy makes root use it);
  - a named volume that the teardown command removes.
- [x] Config writer: builds upstream's `config.yaml` with exactly the keys upstream reads (`deepseek.model`, `deepseek.api_key`, `deepseek.base_url`, `glm.model`, `glm.base_url`), using `yaml.safe_dump`, into the work directory. Values come from environment variables. `deepseek.api_key` is a fixed non-secret placeholder, since vLLM runs without `--api-key`. Driver scripts run with that directory as the working directory and upstream on `sys.path`. That means both the clone's root (for `prompt`, `tools` and `database_utils`) and its `GraphExtraction/`, whose `chunk.py` imports `_utils` as a top-level module.
- [x] Model adapter: an `InstanceManager` from upstream's `tools.utils`, pointed at the chat vLLM instance and wrapped so that every call:
  - adds `temperature=0` and the configured `seed`;
  - logs the prompt length in `cl100k_base` tokens (measured after the call, on the messages as sent) and keeps the maximum;
  - counts empty responses (upstream swallows request errors, including vLLM rejecting an over-length request, and returns `""`).
- [x] `check` command: verifies the upstream commit and a clean upstream working tree, a PyMySQL login from the harness venv with upstream's credentials, the chat model answering, the embedding endpoint returning vectors of length 1024, and both instances' `/metrics` endpoints (all three counters on the chat instance; on the embedding instance a missing `vllm:generation_tokens_total` is reported, not failed). Fails with a message naming what is wrong.
- [x] `scripts/spikes/leanrag/pytest.ini`, so the harness's tests do not pick up the repository's pytest configuration (whose `--disable-socket` needs `pytest-socket`). The harness test command, documented in the README and used by V3 to V6: `cd scripts/spikes/leanrag && TIKTOKEN_CACHE_DIR=<work>/tiktoken <venv>/bin/pytest -q`.
- [x] `README.md` in the harness:
  - prerequisites (Docker, an NVIDIA GPU, vLLM);
  - the two `vllm serve` command lines for one RTX 4090 (memory split, `--max-model-len 32768`, `--kv-cache-dtype fp8`, `--runner pooling` for the embedding model, the dev and baseline chat models), and the 16k fallback;
  - the environment variables and the test command;
  - the full run order: setup, check, generate, chunk, synthetic builds ×3, queries, measurement, `mix` download, chunk and build, `mix` queries and judge, teardown. Steps whose commands later groups build are described and marked; each later group adds its command to the README when it builds it.
- [x] `pyproject.toml`: per-file ignore of `S101` for the harness's tests, so `ruff check .` stays clean.
- [x] Tests (harness venv, written first): with `requests.post` replaced by a fake transport, the adapter sends `temperature=0`, the configured `seed` and upstream's `enable_thinking: False` on every call, counts an error or empty response, and records the longest prompt. The config writer emits exactly the five keys and no secret.

## Group 2: Corpus spec and generator
- [ ] `tests/fixtures/leanrag_baseline/corpus_spec.yaml`: 40 article entries in the `fin-model-evaluation` domain (walk-forward and purged or combinatorial cross-validation, embargoes, deflated Sharpe ratio and probability of backtest overfitting, look-ahead, survivorship and target leakage, normalisation leaks, hyperparameter search and multiple testing). Each entry has a stable ID `synthetic:NN`, a title, fictional authors and venue, a section outline, and a target length of about 3,000 words. Planted items, each with an ID, a `kind` (`fact`, `disagreement`, `canary`, `metachar`) and the section it goes in:
  - 2–3 planted facts per article, each a full sentence with unique fictional specifics (numbers, method names).
  - At least 5 disagreement pairs: two articles plant contradictory facts on the same question.
  - 4 canary articles with distinct payload forms: a direct instruction in body text, an instruction posing as an editorial note, an instruction inside a reference entry, and an instruction to include a URL. Each carries a unique token `RKC-CANARY-<hex>`, and URLs use the `.invalid` TLD.
  - At least 3 method or dataset names containing SQL, YAML and shell metacharacters (quotes, `;`, `--`, backticks, `$(...)`, `: `), used consistently in their articles.
- [ ] `tests/fixtures/leanrag_baseline/questions.yaml`: 15–20 questions with ID, text, kind (`fact`, `disagreement`, `multi-hop`, `seed`, `negative`), expected planted-fact IDs and `expect_strings` (values a correct answer contains). The 3 `docs/topics.md` questions for `fin-model-evaluation` are included as `seed`, at least 2 questions are `negative` (not answerable from the corpus), and every disagreement pair is asked at least once. Status `draft` until the owner approves (Group 4).
- [ ] Generator script:
  - For each article, asks the chat model for each section's prose, given the outline and the planted items for that section.
  - Inserts each planted sentence and canary payload verbatim at a paragraph boundary.
  - Applies NFKC and whitespace normalisation (paragraphs separated by one blank line, no trailing spaces) and verifies each planted string occurs exactly once.
  - Records the model, its revision and the seed.
  - Writes `articles/synthetic-NN.txt` and `articles.jsonl` (ID, title, fictional authors, `synthetic: true`, `generated_by`, planted items with `kind` and character offsets into the final text). Offsets are computed after normalisation.
- [ ] Tests (harness venv, written first), with a scripted fake model:
  - insertion places each planted string verbatim at a paragraph boundary and records offsets that slice back to it exactly;
  - normalisation is idempotent and leaves planted strings intact;
  - a planted string the model's prose happens to repeat is detected and fails the article;
  - canary tokens and `.invalid` URLs survive normalisation unchanged.

## Group 3: Chunk export and offset map
- [ ] Chunk script: runs upstream's `file_chunk.chunk_documents` unchanged (`max_token_size=1024`, `overlap_token_size=128`, `cl100k_base`) over the articles in ID order. Writes its output unchanged as `chunks.json`, plus `chunk_map.jsonl` with, per chunk, the article ID, window index, token start and end, character start and end into the article text, and a `split_char` flag.
- [ ] Offset mapper:
  - Re-encodes each article with the same tiktoken encoding and maps token windows to byte offsets, then to character offsets.
  - A window that starts or ends inside a multi-byte character (whose decoded text then has U+FFFD at that edge) is widened to whole characters and gets `split_char` set.
  - Verifies that each mapped span, after upstream's own post-processing (`strip()`, then removing `\n`), equals the chunk's `text`. For flagged windows, the comparison drops the partial character from the span's edge and the U+FFFD from the chunk text's edge.
  - Verifies that `md5` of the decoded window equals `hash_code`.
  - Maps several chunks with the same `hash_code` to several spans (upstream keys chunks by hash).
  - The number of flagged windows is reported.
- [ ] Tests (harness venv, written first): ASCII text; multi-byte characters (`é`, `—`, `β`) at and across window boundaries, including a flagged window and its edge comparison; overlapping windows; a final short window; an article shorter than one window; duplicate chunk text in two articles giving one `hash_code` with two spans; a span whose post-processed text does not match the chunk text fails loudly.

## Group 4: Corpus generation, approval and the fixture-integrity test (owner runs the model)
- [ ] Owner runs the generator with the baseline chat model and reviews a sample of articles. The agent fixes generator problems the review finds and regenerates.
- [ ] Owner reviews and approves `questions.yaml` (status `approved`, with the date), editing it as needed before any baseline build.
- [ ] Run the chunk script and commit:
  - the corpus (`articles/`, `articles.jsonl`), `chunks.json` and `chunk_map.jsonl`;
  - a fixture `README.md` that says the corpus is synthetic and model-generated (model, revision, seed), contains no third-party text and no upstream code or prompts, and describes every file and its schema.
- [ ] Main-suite test `tests/test_leanrag_baseline_fixture.py` (stdlib only, offline, written first against the committed files):
  - every article in `articles.jsonl` has a text file and `synthetic: true`;
  - every planted item's offsets slice to its text, and its text occurs exactly once in the article;
  - the planted items meet R4's counts by `kind`;
  - every article text is unchanged by NFKC normalisation (T10);
  - every `chunk_map` span lies within its article and, after upstream's post-processing and the `split_char` edge rule, equals the matching chunk text in `chunks.json`;
  - every chunk is mapped;
  - the fixture directory holds only `.txt`, `.json`, `.jsonl`, `.yaml` and `.md` files.

## Group 5: Build and query drivers
- [ ] Build driver: for one build, given a chunks file and a build name, runs GraphExtraction's `triple_extraction` and `deal_triple.deal_duplicate_entity`, then `build_graph.hierarchical_clustering`, with upstream's default parameters.
  - Each build starts from fresh, empty directories, and `deal_duplicate_entity` writes to a different directory from the one it reads, because upstream's `write_jsonl` appends.
  - The build's working directory has a basename that is a valid unquoted MySQL identifier (for example `synthetic_1`, `mix_1`), because upstream uses that basename as the database name in interpolated SQL.
  - After clustering, it asserts that `<working_dir>/milvus_demo.db` exists. Upstream catches vector-index errors and only prints them, and its search then falls back to a hard-coded path.
  - It scans the build output for upstream's printed SQL errors (including batch rollbacks from relation endpoints longer than 190 characters) and records them.
  - Each stage's wall time, empty-response count, longest prompt, and request, prompt-token and generation-token deltas from both vLLM instances' `/metrics` (`vllm:request_success_total`, `vllm:prompt_tokens_total`, `vllm:generation_tokens_total`) go to a per-build log.
  - Exports the build: extraction outputs (`entity.jsonl`, `relation.jsonl`), MySQL tables as JSONL (entities with level and parent, relations, communities), and the hierarchy shape (levels and node count per level). The Milvus file is not exported.
- [ ] Query driver: for each question, embeds the question and calls `search_vector_search`, `get_entity_description`, `get_reasoning_chain`, `get_aggregation_description` and `get_text_units` with upstream's `__main__` settings (`topk=10`, `level_mode=1`, `k=5`). It assembles the same context string `query_graph` builds and makes the same `rag_response` answer call.
  - Writes one JSONL record per question: retrieved entities, reasoning paths, aggregation nodes, text-unit hashes (mapped to article spans through `chunk_map` for the synthetic corpus), the context string (synthetic corpus only) and the answer.
  - A `--compare-query-graph` check runs upstream's `query_graph` on one question and asserts the context string is identical.
- [ ] Dev run: build and query end to end with Qwen3-4B on 5 synthetic articles and 3 questions, outputs in the work directory only. Records whether the 32k context and both instances fit on the GPU with the baseline chat model loaded.
- [ ] Tests (harness venv, written first): the build-name check rejects names that are not valid unquoted MySQL identifiers; the SQL-error scanner finds upstream's error and rollback prints in a recorded log sample; the `/metrics` delta parser works on a recorded Prometheus text sample with labelled `request_success` counters.

## Group 6: Measurements and tolerance band
- [ ] Keyword baseline: SQLite FTS5 with BM25 over the same chunks (`sqlite3` from the standard library), top 5 per question, recorded beside the LeanRAG results. The query is built from the question's word tokens, each double-quoted, joined by `OR`, and bound as a parameter, so FTS5 syntax characters in questions cannot change its meaning.
- [ ] Measurement script, per synthetic build:
  - planted-fact recall (a retrieved text unit's span overlaps an expected planted span) for LeanRAG and FTS5, and `expect_strings` hits in answers;
  - disagreement: whether both sides of each pair are retrieved for its question, and whether both contradictory values survive in some generated community summary;
  - canaries: each token or `.invalid` URL found, case-insensitively, in generated text (entity names, entity and relation descriptions, community summaries, answers), split into "inside a node built from the canary article" and "spread to other nodes or answers";
  - metacharacter names: whether each survives extraction and storage after upstream's own normalisation (upper-casing, `html.unescape`, removal of `"`), with what upstream strips reported separately, plus SQL errors from the build log;
  - traceability: the share of retrieved text units that map to exactly one span, to several spans, or to a flagged window.
- [ ] Across the three synthetic builds:
  - the outcome metrics' per-build values with min, mean and max;
  - per question, the Jaccard of text-unit sets and of entity sets for each of the three pairs, entity-set overlap, hierarchy shape differences, and whether extraction outputs were identical (all for information).

  Writes `metrics.json` per build and `tolerance.json` with these values and the proposed outcome-based parity rule from the Approach.
- [ ] Tests (harness venv, written first): Jaccard and overlap helpers; span-overlap recall against hand-made spans; case-insensitive canary detection and the inside-versus-spread split on hand-made nodes, including an upper-cased entity name; metacharacter comparison after upstream's normalisation; the FTS5 query builder with `?`, `'`, `-` and `"` in questions and the baseline on a three-chunk toy corpus; `tolerance.json` and the parity rule from three hand-made metric sets.

## Group 7: UltraDomain `mix` benchmark
- [ ] Download script: fetches `mix.jsonl` from `TommyChien/UltraDomain` at revision `aa8a51d523f8fc3c5a0ab90dd16b7f6b9dbb5d0d` into the gitignored work directory, verifies its SHA-256 against the value recorded in the harness, and refuses to continue on a mismatch. The first download records the hash. Nothing from the dataset is committed.
- [ ] Chunking: runs upstream's `chunk_documents` on `mix.jsonl` exactly as its `file_chunk.py` `__main__` does (the `context` of every record that has an `input`, 1024/128). It compares the multiset of `hash_code`s with the `datasets/mix/mix_chunk.json` shipped in the upstream clone and records whether they are identical.
- [ ] Questions: the 130 `input` fields of `mix.jsonl`, in file order, keyed by their index and the SHA-256 of the question text.
- [ ] Judge script: given two answer sets for the same questions, asks the chat model, with our own prompt, which answer is better on comprehensiveness, diversity, empowerment and overall, as structured JSON. Every question is judged in both answer orders. It reports win rates per criterion, per order and averaged, with parse failures counted and excluded. The prompt is written for this harness and copies nothing from upstream's `evaluate_score.py`.
- [ ] Dev run: the `mix` path with Qwen3-4B on the first 50 chunks and 5 questions, and the judge on those 5, outputs in the work directory only.
- [ ] Tests (harness venv, written first): hash verification refuses a modified file; question keys are stable; the judge's parser handles valid JSON, invalid JSON (counted as a failure) and position swaps; win rates over both orders on a hand-made set of verdicts.

## Group 8: Baseline runs (owner runs the builds)
- [ ] With the baseline models served, run `check`, then three synthetic builds and the query driver for each build. Run `--compare-query-graph` once.
- [ ] Run the measurement script and commit `tests/fixtures/leanrag_baseline/builds/synthetic-1..3/` (exports, query results, `metrics.json`, the per-build log) and `tolerance.json`.
- [ ] Run the `mix` download, chunking, one build and the 130 queries. Then run the judge: our `mix` answers against upstream's published `datasets/mix/mix_lean_answer.jsonl`, matched by question text.
- [ ] Commit `tests/fixtures/leanrag_baseline/mix/`:
  - the chunk-hash comparison result;
  - per question, the question key, retrieved entity names, text-unit hashes and our answer;
  - the judge's verdicts and win rates;
  - the build's cost log, hierarchy shape and `metrics.json`.

  No `mix` source text, context strings or graph exports are committed.
- [ ] Confirm `git -C` on the upstream clone reports no changes.
- [ ] Record the exact environment in the fixture README:
  - upstream commit;
  - chat, dev and embedding model repos with revisions and quantisation;
  - vLLM version and both `serve` command lines (including the context length and KV-cache dtype actually used);
  - GPU and driver; MySQL image tag; Python version of the harness venv; seed;
  - the UltraDomain revision and `mix.jsonl` SHA-256.
- [ ] Tests: the main suite (including the fixture-integrity test) and `scripts/check.sh` pass with the build outputs committed.

## Group 9: Findings document and parity rule
- [ ] `docs/spikes/leanrag.md`, written in our own words, with no upstream code or prompts:
  - setup and environment (pointing to the fixture README) and the licence finding;
  - input format and chunking (what upstream keeps and drops, the offset map, flagged windows); embedding dimension;
  - traceability findings;
  - build cost per article and per build for both benchmarks (requests, tokens, wall time, longest prompt), extrapolated to 100 and 1,000 articles;
  - stability and the tolerance band; disagreement survival; canary and metacharacter results;
  - retrieval against FTS5;
  - a per-question table (kind, LeanRAG recall per build, FTS5 recall, answer hits);
  - the `mix` results (chunk-hash match, win rates against upstream's published answers);
  - limitations (synthetic, clean text, one domain, one model family, 40 articles, one `mix` build, an LLM judge using the same model family).

  It also has two named sections:
  - "Implications for the reimplementation": what phase 8 must add or do differently, based on the findings. For example: offsets, newline handling, parameterised SQL where upstream interpolates, silent empty responses and batch rollbacks, gleaning calls that truncate the earlier prompt to 3,000 tokens, extraction that runs serially despite `asyncio`, and Windows support of the vector index.
  - "Decision": both baselines are recorded, and phase 8 proceeds, with the approved parity rule as its go/no-go.
- [ ] Owner reviews the proposed parity rule and its numbers in `tolerance.json` and the `mix` judge results, adjusts them if needed, and marks the rule approved (with the date) in `tolerance.json` and the doc.
- [ ] `specs/roadmap.md`: phases 2 and 8 were reworded in the spec commit. Update them only if the findings change something (for example the corpus size actually used).
- [ ] `specs/tech-stack.md`: in Project structure, name `tests/fixtures/leanrag_baseline/` as the engine's parity baseline, which outlives `scripts/spikes/leanrag/`.
- [ ] Tests: none new; `scripts/check.sh` passes.

## Edge cases
- The model's prose already contains a planted string, so it would occur twice → the generator fails that article. The owner regenerates it with another seed and the seed is recorded.
- A tiktoken window boundary falls inside a multi-byte character → the span is widened to whole characters and `split_char` is set. Integrity checks drop the partial character and the U+FFFD at that edge before comparing.
- Two articles produce an identical chunk → one `hash_code` in upstream's dict, several spans in `chunk_map`. Traceability counts it as ambiguous.
- A chat request fails or exceeds `--max-model-len` → upstream returns `""` silently. The adapter counts it and the build log reports it with the longest prompt. A build with any empty responses is rerun before it counts toward the baseline, unless the owner accepts it and the doc says so. Requests that repeat over the limit on a rerun are a finding about upstream's prompt sizes, not a reason to rerun again.
- The 32k context with the fp8 KV cache does not fit next to the embedding instance → the owner falls back to 16,384, records it, and over-length requests become findings.
- The embedding endpoint returns a vector length other than 1024 → `check` fails before any build.
- MySQL is not reachable, the port is taken, or PyMySQL cannot log in → `check` fails, naming `127.0.0.1:4321` and the cause.
- `milvus_demo.db` is missing after clustering → the build fails, since upstream's search would silently read a hard-coded path instead.
- The synthetic builds turn out identical (temperature 0 is deterministic on this stack, and UMAP happens to agree) → the band collapses to a point and is recorded as is. The outcome rule still uses the worst build's values.
- A metacharacter name breaks the build → recorded as a finding with the error. The baseline is rebuilt without that name only if the owner decides so, and the doc says which variant the band comes from.
- The `mix.jsonl` hash differs from the recorded one, or the revision is gone → stop and ask the owner. Never substitute another revision silently.
- The `mix` chunk hashes differ from upstream's shipped `mix_chunk.json` → recorded as a finding (dataset revision or chunker usage differs). The owner decides whether the `mix` build proceeds.
- A published `mix` answer has no matching question text → that question is excluded from the sanity judge and counted.
- An upstream `__main__` or module-level code reads a hard-coded path → the driver supplies the value through upstream's own parameters or the working directory, never by editing upstream. Module globals that upstream's own `__main__` blocks set (`deal_triple.use_llm`, `build_graph.WORKING_DIR`) are set by the driver the same way, since the drivers replace those blocks (R2). If no such route exists, stop and ask the owner.
