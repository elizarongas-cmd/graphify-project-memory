# Architecture

Graphify Project Memory (GPM) is a lightweight companion layer for software projects that combines operational continuity with structural code intelligence.

Its architecture is intentionally narrow. GPM does not attempt to replace Git, Graphify, source code, or existing agent-memory frameworks. Instead, it coordinates them so an agent can recover the minimum context required to continue work without repeatedly loading an entire repository.

## System boundaries

The system has four sources of truth, each with a distinct responsibility.

### Git

Git is the authority for source history.

It provides:

- reviewable changes;
- commits and branches;
- rollback and recovery;
- source revision identity;
- a durable history of what changed.

Project Memory never replaces Git history.

### Graphify

Graphify is the authority for derived project structure.

It provides:

- code and document graph extraction;
- relationships between symbols and files;
- path and impact queries;
- graph traversal;
- structural context;
- Work Memory and reflections where supported;
- incremental graph maintenance.

GPM consumes Graphify capabilities instead of implementing a second parser, AST, or knowledge graph.

### Project Memory

Project Memory is the authority for operational continuity.

It stores and retrieves:

- project objective;
- current phase;
- active task;
- next action;
- work items;
- issues;
- durable decisions;
- durable facts;
- checkpoints;
- provenance;
- freshness baselines;
- retrieval metrics;
- consolidated summaries.

Its job is to answer questions such as:

- Where did the project stop?
- What should happen next?
- Which decisions are still active?
- Which facts are verified?
- Does stored context still correspond to the current source?
- When should retrieval escalate to Graphify or source evidence?

### Source code

Source code remains the final evidence layer.

When memory and graph structure are insufficient, GPM can hydrate narrow source ranges instead of loading whole files by default.

The retrieval chain is therefore:

```text
Project Memory
      ↓
Graphify
      ↓
narrow source evidence
```

This produces a reversible path from compact context back to structural and source-level evidence.

## Core design

### Operational state

Each project receives its own `.project-memory` directory.

The durable state may include:

```text
.project-memory/
├── config.json
├── baseline.json
├── state.json
├── work-items.json
├── issues.json
├── decisions.jsonl
├── facts.jsonl
├── checkpoints.jsonl
├── graph-state.json
└── summaries/
```

Local telemetry such as query metrics and source-read traces can remain unversioned.

### Adaptive retrieval

Adaptive retrieval starts with the smallest useful context.

A typical query proceeds through these stages:

1. Retrieve compact Project Memory.
2. Measure whether memory coverage is sufficient.
3. Escalate to Graphify when the question is structural or memory coverage is low.
4. Hydrate narrow source ranges when direct evidence is still required.

This keeps source reading proportional to the task instead of proportional to repository size.

### Freshness

Freshness distinguishes source changes from metadata changes.

GPM tracks:

- `source_revision`: the source revision represented by the current baseline;
- `observed_head`: the Git HEAD observed when state was captured;
- `source_content_sha256`: a content fingerprint of source-significant files;
- graph and manifest hashes for diagnostic drift.

A metadata-only commit can therefore advance Git HEAD without falsely claiming that source code changed.

### Fingerprint normalization

Project Memory may manage a marked block inside `AGENTS.md`.

Only that managed block is source-neutral for fingerprinting.

Human-authored content outside the managed block remains source-significant.

This preserves two properties at once:

- GPM may update its own instructions without creating false source drift.
- Human edits to project instructions still affect freshness.

### Durable facts

Facts have deterministic identity derived from their canonical subject, predicate, and value.

A fact may move through lifecycle states such as:

```text
active
superseded
revoked
stale
needs_validation
```

A changed value for the same subject/predicate supersedes the previous active value while preserving history.

Facts can carry provenance such as:

```text
source_type
path
source_label
line_start
line_end
source_revision
observed_at
confidence
```

This keeps memory assertions traceable to evidence.

### Conflict validation

Source-backed facts are not silently trusted forever.

When source evidence disappears or the source revision advances, validation may mark a fact `needs_validation`.

Queries that depend on such facts can then escalate to Graphify or source evidence.

This favors conservative uncertainty over stale confidence.

### Checkpoints

A checkpoint records a meaningful project state without creating a Git commit.

A checkpoint can capture:

- current operational state;
- source and graph state;
- fact validation results;
- consolidated memory;
- a human-readable summary.

Git commits remain a separate, explicit action.

## Graph maintenance

Graphify can be updated manually:

```text
graphify update .
```

or kept synchronized with code changes:

```text
graphify watch .
```

GPM does not require its own background daemon.

Operational memory is updated deliberately at meaningful moments rather than on every file write.

## Context efficiency

The architecture is designed around context minimization, not billing claims.

Metrics such as:

```text
context_avoided_estimate
context_reduction_percent
```

describe local retrieval reduction.

They should not be interpreted as guaranteed provider-billed token savings.

## Non-goals

Graphify Project Memory intentionally does not implement:

- a second AST;
- a second knowledge graph;
- a vector database;
- embeddings;
- a duplicate MCP server;
- autonomous multi-agent orchestration;
- a mandatory background daemon;
- a replacement for Git;
- a replacement for source code.

These boundaries keep the system small, auditable, and composable.

## Architectural principle

The central principle is:

> Memory should preserve operational continuity, Graphify should preserve structural understanding, Git should preserve history, and source code should remain the final evidence.

That division of responsibility allows GPM to recover project context efficiently without duplicating systems that already solve adjacent problems.
