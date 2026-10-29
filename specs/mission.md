# Mission

## Vision
Research Knowledge Curator (`rkc`) is an agent-maintained, evidence-anchored research knowledge base that any developer can add to a project. Research agents pull new papers on a schedule, keep only what matters to a context the user approved, store it as claims that each point to a verified quote in a source, keep disagreement visible, and record why every change was made. Coding agents and people query it through a CLI. There is no GUI and no chat application.

## Audience
- **Developers who work with coding agents** (Claude Code and similar) and want a living, citable literature base inside their project. They install `rkc` as an isolated tool, and their coding agent sets it up through the shipped `rkc-setup` skill: it analyzes the project, interviews the user, writes the research-agent configuration, and asks the user to approve it.
- **Coding agents** that consume query results. They are a first-class audience, so every command works non-interactively and supports `--json`.
- **The owner**, who is also the first user, with five topics (see `docs/topics.md`). Their real use sets the quality bar.

## Problem
Keeping up with research on a fast-moving topic means reading feeds, judging relevance, remembering what was already claimed, and noticing when new work contradicts old work. LLM summaries of papers lose provenance, average away disagreement, invent quotes, and can be steered by text hidden in the papers they read. A developer who wants research grounding for a project has no tool that is scheduled, grounded in verifiable quotes, history-preserving, agent-operable, and defended against prompt injection.

## Scope
- In:
  - Scheduled, deterministic, duplicate-free intake from arXiv, and from OpenAlex when the user supplies a key, with catch-up after downtime.
  - Relevance judgement against a user-approved context, and curation with a devil's-advocate step.
  - Claims, conflicts, refutations and ambiguity, each grounded in a quote mechanically verified against the cached source.
  - Full history: what changed, when and why, and retracting a bad run.
  - CLI queries with machine-readable output, using hierarchical retrieval (LeanRAG) behind a replaceable engine interface.
  - Installation into any project as an isolated tool, with several research agents per cluster and any number of clusters.
  - Any model reachable by base URL, key and model name.
  - Prompt-injection defense: a mandatory input guard before anything is stored, an output guard on results (on by default), and enforcement controls in code that contain whatever gets past both, proven by tests.
  - Local files (literature, experiment reports, notes) as evidence.
- Out (non-goals):
  - A GUI, a chat interface, or an MCP server (an MCP wrapper over the CLI is future work).
  - Confidentiality of data sent to the model endpoints the user configures. The user chooses the endpoints, and `rkc` neither warns nor restricts.
  - Open-web fetching, and sources other than arXiv, OpenAlex and local files (Crossref, Semantic Scholar, Wikipedia, Wikidata and Google Scholar are deferred).
  - Tamper-evidence (hash chains, signatures), true valid-time intervals, a topic taxonomy inside a cluster, cross-cluster queries, currency budgets, and a human review gate on every change.
  - Writing an in-house retrieval engine, or forking LeanRAG without a measured reason.
  - Modifying the host project. `rkc` writes only inside its cluster directory, and writes skills only to a directory the user names.

## Success
- A developer who has never seen the project installs it with `uv tool install`, asks their coding agent to add a research agent, and gets a scheduled, approved agent through `rkc-setup` without editing YAML by hand.
- The owner's five clusters run on a schedule. The `fin-model-evaluation` cluster answers its example questions with claims backed by verified quotes, and shows the disagreements that exist in the literature.
- No claim reaches the store without a quote that matches its cached source exactly.
- The security smoke suite passes offline. A deliberately vulnerable curator stub fails it, which shows the suite can catch real failures.
- A bad run can be retracted, and `rkc log` and `rkc diff` explain every change.
- The package is published on PyPI under the MIT license, with docs that state what the system does and does not establish.

## Tone & principles
- **The best part is no part. Do not reinvent the wheel.** Every component must serve a requirement in Scope. Mature libraries and the published LeanRAG are used instead of building our own.
- **The store owns the facts.** Engines only suggest which claims are relevant. Status, evidence and history always come from the store.
- **Nothing is deleted from the store.** Changes are new rows in changesets. The raw cache is never edited, and the only deletions are cache copies of content the input guard blocks.
- **Everything fetched or written by a model is untrusted data**, scanned at every hop and never used to build paths, URLs, SQL or commands. Prompt wording and classifiers are mitigations. The real defense is enforcement in code.
- **Runs are idempotent and resumable.** Watermarks move only on success.
- **Honest about limits.** Results are marked untrusted and stale where they are. The docs say what injection detection cannot catch.
