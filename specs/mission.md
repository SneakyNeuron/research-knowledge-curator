# Mission

## Vision
Research Knowledge Curator (`rkc`) is an agent-maintained, injection-defended research knowledge base that any developer can add to a project. Research agents pull new papers on a schedule, keep only what is relevant to a context the user approved, check them for prompt-injection attacks, and index the original full text, unchanged, in a hierarchical retrieval engine (LeanRAG). The original text is the ground truth: its lowest level is the source text itself, and later layers add notes to it rather than rewriting it. Coding agents and people query it through a CLI. There is no GUI and no chat application.

## Audience
- **Developers who work with coding agents** (Claude Code and similar) and want a living, citable literature base inside their project. They install `rkc` as an isolated tool, and their coding agent sets it up through the shipped `rkc-setup` skill: it analyzes the project, interviews the user, writes the research-agent configuration, and asks the user to approve it.
- **Coding agents** that consume query results. They are a first-class audience, so every command works non-interactively and supports `--json`.
- **The owner**, who is also the first user, with five topics (see `docs/topics.md`). Their real use sets the quality bar.

## Problem
Keeping up with research on a fast-moving topic means reading feeds, judging relevance and remembering what was already read. LLM summaries of papers lose provenance, average away disagreement, invent quotes, and can be steered by text hidden in the papers they read. A developer who wants research grounding for a project has no tool that is scheduled, keeps the original text as the source of truth, is agent-operable, and is defended against prompt injection.

## Scope
- In (MVP):
  - Scheduled, deterministic, duplicate-free intake from arXiv, and from OpenAlex when the user supplies a key, with catch-up after downtime. Papers are fetched as full text (PDF) from provider-controlled endpoints only, falling back to the abstract when no full text is available.
  - Relevance judgement against a user-approved context: one structured model call per paper, before anything is indexed.
  - The original text, unchanged, as the lowest level of the knowledge base, with a seam for notes attached to it later.
  - History of intake: what was added, when and why (the relevance reason), and retracting a bad run.
  - CLI queries with machine-readable output, using hierarchical retrieval (LeanRAG) behind a replaceable engine interface. Every result says which text is verbatim source text (with its source ID and location) and which is model-generated.
  - Installation into any project as an isolated tool, with several research agents per cluster and any number of clusters.
  - Any model reachable by base URL, key and model name.
  - Prompt-injection defense: a mandatory input guard before anything is stored or indexed, an output guard on results (on by default), and enforcement controls in code that contain whatever gets past both, proven by tests.
  - Local files (literature, experiment reports, notes) as sources, through the same guard.
  - Skills that let a coding agent set up, query and operate `rkc`.
- Later (after the MVP, see the roadmap):
  - Notes: adding knowledge on top of the original text (human or agent notes, metadata, agent-written syntheses built from the knowledge base). How notes are created is deliberately undecided. Whatever the mechanism, notes never edit the original text and are always marked as notes, not sources.
  - Claim extraction, conflict and refutation links, and a devil's-advocate step (the archived design's curation graph).
- Out (non-goals):
  - A GUI, a chat interface, or an MCP server (an MCP wrapper over the CLI is future work).
  - Confidentiality of data sent to the model endpoints the user configures. The user chooses the endpoints, and `rkc` neither warns nor restricts.
  - Open-web fetching (including publisher URLs found in metadata), and sources other than arXiv, OpenAlex and local files (Crossref, Semantic Scholar, Wikipedia, Wikidata and Google Scholar are deferred).
  - Tamper-evidence (hash chains, signatures), a topic taxonomy inside a cluster, cross-cluster queries, currency budgets, and a human review gate on every change.
  - Writing an in-house retrieval engine, or forking LeanRAG without a measured reason.
  - Modifying the host project. `rkc` writes only inside its cluster directory, and writes skills only to a directory the user names.

## Success
- A developer who has never seen the project installs it with `uv tool install`, asks their coding agent to add a research agent, and gets a scheduled, approved agent through `rkc-setup` without editing YAML by hand.
- The owner's five clusters run on a schedule. The `fin-model-evaluation` cluster answers its example questions with results that point to verbatim passages of the papers they come from.
- Nothing reaches the cache, the store or the engine without passing the input guard, and no query result presents model-generated text as source text.
- The security smoke suite passes offline. A deliberately vulnerable stub fails it, which shows the suite can catch real failures.
- A bad run can be retracted, and `rkc log` explains every intake decision.
- The package is published on PyPI under the MIT license, with docs that state what the system does and does not establish.

## Tone & principles
- **The best part is no part. Do not reinvent the wheel.** Every component must serve a requirement in Scope. Mature libraries and the published LeanRAG are used instead of building our own.
- **The original text is the ground truth.** It is stored and indexed unchanged. Anything a model writes (relevance reasons, engine summaries, later notes) sits on top of it, is marked as generated, and points back to the source text.
- **The store owns the facts.** The engine only suggests which passages are relevant. Source identity, intake decisions, retractions, bans and history always come from the store.
- **Nothing is deleted from the store.** Changes are new rows in changesets. The raw cache is never edited, and the only deletions are cache copies of content the input guard blocks.
- **Everything fetched or written by a model is untrusted data**, scanned at every hop and never used to build paths, URLs, SQL or commands. Prompt wording and classifiers are mitigations. The real defense is enforcement in code.
- **Runs are idempotent and resumable.** Watermarks move only on success.
- **Honest about limits.** Results are marked untrusted and stale where they are. The docs say what injection detection cannot catch.
