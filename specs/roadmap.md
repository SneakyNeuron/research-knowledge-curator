# Roadmap

Each phase is one feature: planned with `/sdd:feature`, built with `/sdd:implement` and closed with `/sdd:validate`. Phases name the sections of the archived design (`specs/backlog/2026-10-28-design-v3.1.md`) worth reading when their feature spec is written. That design predates the 2026-11-02 pivot from claim curation to original-text indexing, so the constitution wins wherever the two differ.

The MVP (phases 1–12) is a secured system that pulls papers, checks them for attacks and relevance, indexes the original text in LeanRAG, and lets agents query it. LeanRAG is now the backbone, so its spike comes first: what it accepts and returns shapes the store and the engine wrapper. The classifier evaluation (phase 5's manual task) needs the owner and network access too, and can start alongside phases 2–4.

## Phase 1: Scaffolding ✅
Spec: specs/features/01-scaffolding/
Goal: a packaged, installable `rkc` with the full quality toolchain and CI in place.
- [x] `pyproject.toml` with `requires-python >=3.12`, both console scripts, MIT license and the dev tools. Fix the scaffold's current `>=3.14` and its hello-world entry point
- [x] `.gitignore`, `.env.example`, `LICENSE`, `CLAUDE.md` (commands, module map, the untrusted-data, store-owns-the-facts and scan-every-hop rules)
- [x] `rkc --version`, `rkc --help`, `rkc version [--json]` and a global `--json` option
- [x] GitHub Actions workflow on Python 3.12 and 3.14
Design reference: "Implementation steps > Step 1", "Naming", "Files to create".

## Phase 2: LeanRAG spike (manual, owner)
Goal: a measured go or no-go on LeanRAG as published, used on original full text.
- [ ] Run LeanRAG at a pinned commit on about 50–100 real full-text papers from `fin-model-evaluation`, and record in `docs/spikes/leanrag.md`: input format and chunking, whether a result can be traced back to the original passage (source ID and offsets), where notes could attach at the lowest level, incremental add and removal versus full rebuild, build cost and time per paper, stability, whether injected text survives its summarizer, and retrieval quality on the cluster's example questions
- [ ] Record the decision and any justified patches. If it fails the go criteria, agree a different existing engine before phase 8
Design reference: "Step 9", "LeanRAG engine".

## Phase 3: Configuration and cluster init
Goal: clusters and research agents can be created, validated, approved and paused.
- [ ] Pydantic models for `cluster.yaml` and agent YAML (context, sources, triage model, caps), with errors that name the file and field
- [ ] Secrets from the environment or `.env`, redaction, and the approval hash over context, sources and specs
- [ ] `rkc init`, `rkc agent add | validate | approve | list`, `rkc pause | resume`
- [ ] ID validation. `approve` needs an interactive terminal
Design reference: "Step 2", "Cluster layout and configuration".

## Phase 4: Intake store and cache
Goal: an append-only record of what entered the knowledge base and why, with the original text kept unchanged.
- [ ] Schema with migrations: sources, intake decisions (with relevance reason), runs and changesets, watermarks, ban list
- [ ] As-of reads, `retract` of a run, and FTS5 over the normalized source text
- [ ] Hash-addressed cache for payloads and extracted text, NFKC and whitespace normalization, offset locators, cache-only deletion
- [ ] `rkc log`, `rkc show <source>`, `rkc verify` (cache integrity by hash)
Design reference: "Step 3", "Step 4", "Knowledge store" (claim tables do not apply).

## Phase 5: Scanner, ban list and sandboxed extraction (input guard)
Goal: poisoned content is detected, banned and deleted before it is stored, indexed or read by a model.
- [ ] Sandboxed text extraction (PDF and local files) with resource limits, an allowlist of readers, and hidden PDF text as a separate view
- [ ] Normalization, recursive decoding, linear-time rules, the classifier interface with a loud rules-only mode, and fail-closed policy
- [ ] Ban actions, the verdict cache, `rkc scan`, `rkc ban list | show | release`, and the output sanitizer exported for later use
- [ ] Security corpus (including poisoned PDFs) and `scripts/scanner_eval.py` (offline with a stub classifier)
- [ ] Manual (owner): run the classifier evaluation and record the default in `docs/spikes/scanner.md`
Design reference: "Step 5", "Injection defense".

## Phase 6: Model layer, relevance triage and `doctor`
Goal: any configured model can be called safely, papers get a relevance decision, and the environment can be diagnosed.
- [ ] Role-based chat models, structured calls with one retry, usage counting and scripted fakes
- [ ] Provenance prompt template with an untrusted block, and the triage call (relevant or not, capped reason)
- [ ] `rkc doctor` (Python, FTS5, cluster, scanner, classifier, Docker, model connectivity, keys by name only)
Design reference: "Step 6", "Models", and triage in "Curation workflow".

## Phase 7: Sources
Goal: papers from arXiv, OpenAlex and local files arrive as guarded, deduplicated full text.
- [ ] `Article`, the adapter protocol, and the arXiv adapter (metadata, watermarks, PDF download within the rate limit)
- [ ] OpenAlex adapter (abstract reconstruction, retraction flag, full text from OpenAlex's content endpoint within its allowance, abstract fallback)
- [ ] Namespaced identity, ban checks, the input guard before any write, and triage before indexing
- [ ] `rkc add-file --as literature|experiment|note`
Design reference: "Step 7", "Sources".

## Phase 8: LeanRAG engine and queries
Goal: `rkc query` returns sanitized, untrusted-marked results through LeanRAG, each labelled as verbatim source text or engine-generated, falling back to keyword search.
- [ ] Engine protocol, `Hit` with the verbatim or generated label and source locators, hydration from the store with the output guard, and a reusable contract test
- [ ] LeanRAG wrapper, Docker compose file, sandboxed build, sync (including removal of retracted sources) and rebuild thresholds
- [ ] `rkc query`, `rkc engine install | sync | status`
Design reference: "Step 10", "Engines", "Retrieval", "LeanRAG engine".

## Phase 9: Run orchestration
Goal: `rkc run` executes an agent end to end, idempotently, with clear exit codes.
- [ ] Lock, approval check, watermarks, dedupe, input guard, triage, caps, `--dry-run`, engine sync, and the run summary
- [ ] Exit codes for caps, locks, approval drift and scanner failure. Respect pause
Design reference: "Step 11", "Caps and dry-run".

## Phase 10: Scheduling
Goal: agents run on cron without touching anything else in the crontab.
- [ ] `rkc schedule install | remove | show`, with a fixed command template and validated IDs
Design reference: "Step 12", "Scheduling".

## Phase 11: Security smoke suite and report
Goal: evidence that the defense contains injection, including payloads the guards miss.
- [ ] Cases, network blocker, instrumented stubs, a deliberately vulnerable stub of the triage and query paths, a regression corpus, a best-of-N budget and a `live` mode
- [ ] Cases for model-generated text presented as source text, and for URLs in fetched content trying to steer downloads
- [ ] `scripts/security_smoke.py` writes the report (results per objective, failures with evidence, benign controls, what is not covered)
Design reference: "Step 13", "Test scenarios", "Injection defense".

## Phase 12: Skills, docs, end-to-end check and release
Goal: a developer installs `rkc` from PyPI and a coding agent sets it up through skills.
- [ ] `rkc-setup`, `rkc-query`, `rkc-ops`, `rkc-report`, and `rkc skills install --target`
- [ ] `docs/limits.md` and a finished README (including Docker for LeanRAG)
- [ ] Automated end-to-end test, a `uv build` wheel that installs with `uv tool install`, and the first PyPI release
Design reference: "Step 14", "Verification".

## Later / unscheduled
- Notes layer on top of the original text: [specs/backlog/2026-11-02-notes-layer.md](backlog/2026-11-02-notes-layer.md).
- Claim curation (claims, conflict and refutation links, devil's advocate, quote verification): archived design, "Curation workflow" and "Step 8".
- An MCP wrapper over the CLI (see the notes-layer backlog file for `mcpc`), more source adapters, more retrieval engines, tamper-evidence, a review gate, and currency budgets.
- The archived design's future-work list: `specs/backlog/2026-10-28-design-v3.1.md` ("Future work").
