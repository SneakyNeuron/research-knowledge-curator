# Notes layer (after the MVP)

Recorded during the 2026-11-02 replan, when the MVP pivoted from claim curation to indexing the original text.

## Idea (owner)
The original texts stay exactly as fetched. Knowledge is extended only by adding notes on top of them, so LeanRAG's lowest level is original text plus notes. Notes could be metadata, human notes, or new documents written by an agent from what the knowledge base already holds. How notes are created is deliberately left open.

## Constraints already agreed
- Notes never modify the cached original text, and are always labelled as notes, never as sources.
- A note attaches to a source, and optionally a location in it (source ID plus offsets).
- Notes are untrusted input like everything else: they pass the input guard before they are stored or indexed.

## Risks to resolve in the feature spec
- **Circular evidence.** An agent writes a synthesis from the knowledge base, it is indexed, and a later query cites it as if it were literature. Generated notes need their own namespace (for example `note:` or `generated:`), must cite source passages that code verifies against the cache, and must never be returned as source text.
- **Recursive injection.** A payload that got past the guard in one paper can be copied into a note and from there into every later note. Scan notes at intake and cap and sanitize their text, and test this with the smoke suite's replication cases.
- **Disagreement.** The archived design kept disagreement visible through conflict links. If that is still wanted, notes (or a later claim layer) are where it lives.

## Related later items
- The archived design's curation graph (claims, conflict and refutation links, devil's advocate, quote verification): `specs/backlog/2026-10-28-design-v3.1.md`, "Curation workflow" and "Step 8".
- An MCP wrapper over the CLI. If it is built, [mcpc](https://github.com/apify/mcp-cli) (Apify's command-line MCP client, npm `@apify/mcpc`, with `--json` output and persistent sessions) is one way for coding agents in shell-only sandboxes to reach it. It does not help the MVP: agents already call `rkc --json` directly, and fetching papers through a third-party MCP server would add a Node runtime and an extra untrusted hop to the intake path.
