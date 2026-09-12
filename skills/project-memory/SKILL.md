---
name: project-memory
description: Use structured operational project memory together with Graphify and Git when work depends on prior decisions, durable facts, tasks, issues, checkpoints, freshness, provenance, source evidence, or adaptive context retrieval.
---

# Project Memory

Use Project Memory for operational continuity, Graphify for structural relationships, and Git for source history.

## Start cheaply

1. Run `gpm status --project <root>` for compact operational state.
2. Run `gpm freshness --project <root>` when prior context may have changed.
3. Run `gpm query "<question>" --adaptive --project <root>` before broad source reads.
4. Let adaptive retrieval escalate memory → Graphify → narrow source ranges when necessary.

Do not broad-read the repository when compact memory or Graphify can answer the question.

## Durable facts and lifecycle

- Use `gpm fact-add <subject> <predicate> <value>` for durable operational facts.
- Attach `--source`, `--start-line` and `--end-line` when concrete evidence exists.
- Use `gpm fact-status` to revoke/stale/restore facts; never erase history simply because a fact changed.
- `gpm validate-facts` conservatively flags source-backed facts that need revalidation.
- A `needs_validation` fact should cause retrieval to escalate rather than be silently trusted.

Graphify's native Work Memory remains appropriate for useful/dead-end/corrected graph-query signals; do not duplicate it into Project Memory facts.

## Decisions and issues

Use `gpm decision` for approved choices and reasons, and `gpm issue` for reproducible problems/resolutions. Add exact source ranges when available.

## Complete material work

If Graphify has not already been updated:

`gpm checkpoint "<outcome>" --project <root>`

If Graphify was updated explicitly:

`gpm checkpoint "<outcome>" --no-graphify --project <root>`

Both forms capture the current source/graph baseline. A checkpoint never authorizes or creates a Git commit.

## Freshness semantics

- source fingerprint changed → stale;
- HEAD changed but source fingerprint identical → fresh with metadata/head-only warning;
- graph/manifest changed while source identical → fresh with graph-drift warning.

`source_revision` is the revision represented by the source baseline; `observed_head` is the Git HEAD seen at capture time.

## Consolidation and reporting

Use `gpm consolidate` to create compact current memory without deleting raw history. Use `gpm report --task <id>` or `--all` to inspect retrieval, hydration and context-reduction metrics.

Treat `context_avoided_estimate` as a local context-reduction estimate, never provider billing.

Read [references/schema.md](references/schema.md) when editing or migrating memory files.


### 0.3.6 freshness note
The Project Memory managed block in root `AGENTS.md` is metadata for freshness purposes. Do not treat a change confined to that block as a source edit. Human content outside the block remains source-significant.
