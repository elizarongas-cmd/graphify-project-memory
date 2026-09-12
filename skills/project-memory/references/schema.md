# Project Memory schema

The project-owned `.project-memory/` directory uses schema version 4.

## Durable/shareable state

- `config.json`: project identity, Graphify location, query budget and migration history.
- `state.json`: objective, phase, current task, active task id and next action.
- `work-items.json`: project work-item records.
- `issues.json`: known problems and resolution state, with optional provenance.
- `decisions.jsonl`: append-only durable decisions with provenance.
- `facts.jsonl`: append-only canonical operational fact events and lifecycle state.
- `checkpoints.jsonl`: append-only completed-work checkpoints, including source/graph baseline metadata.
- `baseline.json`: latest Graphify benchmark used for context-reduction comparisons.
- `graph-state.json`: source revision, observed HEAD, source fingerprint, graph and manifest baseline used by `gpm freshness`.
- `summaries/*.md`: compact project-owned summaries, including optional `consolidated.md`.

## Fact lifecycle

Facts use deterministic identity and one of:

- `active`
- `superseded`
- `revoked`
- `stale`
- `needs_validation`

A new value for the same canonical subject/predicate supersedes the previous active value without deleting history.

## Provenance

Durable records may include:

- `source_type`
- `path` or `source_label`
- `line_start` / `line_end`
- `source_revision`
- `observed_at`

Project Memory uses provenance to revalidate operational memory; Graphify remains the structural-code authority.

## Local operational telemetry by default

- `metrics.jsonl`: task-scoped retrieval measurements, coverage, escalation, hydration and estimated context reduction.
- `source-reads.jsonl`: explicitly read or automatically hydrated source ranges. Content is never copied here; only metadata/token estimates are recorded.

`metrics.jsonl` and `source-reads.jsonl` are ignored by Git by default because they can be noisy and machine/session specific.

Graphify's runtime/cache/native personal memory/reflections remain Graphify-local artifacts. Recommended shareable Graphify artifacts are `graph.json`, `manifest.json` and `GRAPH_REPORT.md`.


## Source fingerprint v2 (0.3.6)

`graph-state.json.git.source_fingerprint_version` is `2` for new baselines. The root `AGENTS.md` Project Memory managed block is normalized out of source-significant content. Human content outside that block remains part of the fingerprint. Legacy baselines are upgraded only when metadata-only equivalence can be proven.
