# Roadmap

Each phase is one feature: planned with `/sdd:feature`, built with `/sdd:implement` and closed with `/sdd:validate`. The phases follow the 14 steps of the archived design (`specs/backlog/2026-10-28-design-v3.1.md`). Each one names the sections of that file to read when its feature spec is written, and the constitution wins wherever the two differ.

Two manual spikes need the owner, network access and, for LeanRAG, real models and Docker: the classifier evaluation (phase 5) and the LeanRAG spike (phase 9). Start them early, alongside phases 1–4. Phases 7–10 depend on them.

## Phase 1: Scaffolding
Spec: specs/features/01-scaffolding/
Goal: a packaged, installable `rkc` with the full quality toolchain and CI in place.
- [ ] `pyproject.toml` with `requires-python >=3.12`, both console scripts, MIT license and the dev tools. Fix the scaffold's current `>=3.14` and its hello-world entry point
- [ ] `.gitignore`, `.env.example`, `LICENSE`, `CLAUDE.md` (commands, module map, the untrusted-data, store-owns-the-facts and scan-every-hop rules)
- [ ] `rkc --version`, `rkc --help`, `rkc version [--json]` and a global `--json` option
- [ ] GitHub Actions workflow on Python 3.12 and 3.14
Design reference: "Implementation steps > Step 1", "Naming", "Files to create".

## Phase 2: Configuration and cluster init
Goal: clusters and research agents can be created, validated, approved and paused.
- [ ] Pydantic models for `cluster.yaml` and agent YAML, with errors that name the file and field
- [ ] Secrets from the environment or `.env`, redaction, and the approval hash over context, sources and specs
- [ ] `rkc init`, `rkc agent add | validate | approve | list`, `rkc pause | resume`
- [ ] ID validation. `approve` needs an interactive terminal
Design reference: "Step 2", "Cluster layout and configuration".

## Phase 3: Claim store
Goal: an append-only, history-preserving store for claims and their evidence.
- [ ] Schema with migrations: sources, claims, evidence, links, changesets, intake log, watermarks, ban list
- [ ] Derived status, the current-claim rule, as-of reads, the FTS5 keyword index, and `retract`
- [ ] `rkc log`, `rkc diff`, `rkc show`
Design reference: "Step 3", "Knowledge store".

## Phase 4: Cache and quote verification
Goal: no claim can cite a quote that is not in its source.
- [ ] Hash-addressed cache with NFKC and whitespace normalization
- [ ] Exact-substring quote verification with a length cap, and locators
- [ ] Cache-only deletion, and `rkc verify`
Design reference: "Step 4".

## Phase 5: Scanner and ban list (input guard)
Goal: poisoned content is detected, banned and deleted before it is stored.
- [ ] Normalization, recursive decoding, linear-time rules, the classifier interface with a loud rules-only mode, and fail-closed policy
- [ ] Ban actions, the verdict cache, `rkc scan`, `rkc ban list | show | release`
- [ ] Sandboxed file parsing, and the output sanitizer exported for later use
- [ ] Security corpus and `scripts/scanner_eval.py` (offline with a stub classifier)
- [ ] Manual (owner): run the classifier evaluation and record the default in `docs/spikes/scanner.md`
Design reference: "Step 5", "Injection defense".

## Phase 6: Model layer and `doctor`
Goal: any configured model can be called safely, and the environment can be diagnosed.
- [ ] Role-based chat models, structured calls with one retry, usage counting and scripted fakes
- [ ] Provenance prompt template with an untrusted block and agent tags
- [ ] `rkc doctor` (Python, FTS5, cluster, scanner, classifier, Docker, model connectivity, keys by name only)
Design reference: "Step 6", "Models".

## Phase 7: Sources
Goal: articles from arXiv, OpenAlex and local files arrive guarded and deduplicated.
- [ ] `Article`, the adapter protocol, and the arXiv and OpenAlex adapters (watermarks, abstract reconstruction, retraction flag)
- [ ] Namespaced identity, ban checks, and the input guard before any write
- [ ] `rkc add-file --as literature|experiment|note`
Design reference: "Step 7", "Sources".

## Phase 8: Curation graph
Goal: an article becomes verified, challenged claims and links, applied in one transaction.
- [ ] LangGraph workflow: triage, recall, propose, challenge, revise, verify, apply
- [ ] Caps on devil's-advocate rounds, mechanical verification, and transactional apply with changesets
Design reference: "Step 8", "Curation workflow".

## Phase 9: LeanRAG spike (manual, owner)
Goal: a measured go or no-go on LeanRAG as published.
- [ ] Run LeanRAG at a pinned commit on about 200 real claims, and record schemas, output shape, cost, stability, conflict survival, scanner results and retrieval quality in `docs/spikes/leanrag.md`
- [ ] Record the decision and any justified patches. If it fails the go criteria, agree a different existing engine before phase 10
Design reference: "Step 9", "LeanRAG engine".

## Phase 10: LeanRAG engine, hydration and queries
Goal: `rkc query` returns hydrated, sanitized, untrusted-marked results through LeanRAG, falling back to keyword search.
- [ ] Engine protocol, `Hit`, hydration with the output guard, and a reusable contract test
- [ ] LeanRAG wrapper, Docker compose file, sandboxed build, and rebuild thresholds
- [ ] `rkc query`, `rkc engine install | sync | status`
Design reference: "Step 10", "Engines", "Retrieval", "LeanRAG engine".

## Phase 11: Run orchestration
Goal: `rkc run` executes an agent end to end, idempotently, with clear exit codes.
- [ ] Lock, approval check, watermarks, dedupe, input guard, caps, `--dry-run`, engine rebuild, and the run summary
- [ ] Exit codes for caps, locks, approval drift and scanner failure. Respect pause
Design reference: "Step 11", "Caps and dry-run".

## Phase 12: Scheduling
Goal: agents run on cron without touching anything else in the crontab.
- [ ] `rkc schedule install | remove | show`, with a fixed command template and validated IDs
Design reference: "Step 12", "Scheduling".

## Phase 13: Security smoke suite and report
Goal: evidence that the defense contains injection, including payloads the guards miss.
- [ ] Cases, network blocker, instrumented stubs, a deliberately vulnerable curator stub, a regression corpus, a best-of-N budget and a `live` mode
- [ ] `scripts/security_smoke.py` writes the report (results per objective, failures with evidence, benign controls, what is not covered)
Design reference: "Step 13", "Test scenarios", "Injection defense".

## Phase 14: Skills, docs, end-to-end check and release
Goal: a developer installs `rkc` from PyPI and a coding agent sets it up through skills.
- [ ] `rkc-setup`, `rkc-query`, `rkc-ops`, `rkc-report`, and `rkc skills install --target`
- [ ] `docs/limits.md` and a finished README (including Docker for LeanRAG)
- [ ] Automated end-to-end test, a `uv build` wheel that installs with `uv tool install`, and the first PyPI release
Design reference: "Step 14", "Verification".

## Later / unscheduled
- Archived design and its future-work list: `specs/backlog/2026-10-28-design-v3.1.md` ("Future work").
- An MCP wrapper over the CLI, more source adapters, more retrieval engines, tamper-evidence, a review gate, and currency budgets.
