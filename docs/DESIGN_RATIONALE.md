# Design Rationale

Graphify Project Memory was designed around one question:

> How can an AI agent resume real software work with enough context to be useful without repeatedly re-reading the entire project?

The answer is not to create another general-purpose memory system. It is to combine a small operational memory with existing structural and version-control systems.

## Why a separate Project Memory layer?

Git can tell us what changed, but it does not directly answer:

- What is the current objective?
- What task is active?
- What should happen next?
- Which unresolved issues matter now?
- Which architectural decisions are still in force?

Graphify can tell us how code is connected, but structural relationships are different from operational continuity.

Project Memory fills that gap.

It stores the small amount of durable project state that an agent needs to resume work intelligently.

## Why Graphify remains the structural authority

Graphify already provides code and document graph extraction, traversal, relationships, query budgets, incremental updates, and related structural capabilities.

Duplicating those features inside GPM would create:

- two structural truth systems;
- duplicated extraction logic;
- additional synchronization problems;
- more maintenance;
- greater context overhead.

For that reason, GPM probes and consumes Graphify capabilities instead of replacing them.

The architectural rule is simple:

> If a question is about structure, prefer Graphify.

## Why Git remains the historical authority

Operational memory is useful, but it should never become the only record of what happened.

Git provides:

- reviewable changes;
- immutable commit history;
- recovery;
- branching;
- diff-based verification.

GPM therefore treats Git as the authoritative source-history system.

A Project Memory checkpoint is not a commit and should never silently create one.

## Why retrieval is progressive

Large projects contain much more information than most tasks require.

Loading all available context can:

- waste tokens;
- bury relevant details;
- increase latency;
- make reasoning less focused.

GPM therefore follows progressive recall:

```text
compact memory
      ↓
structural graph
      ↓
exact source evidence
```

The system only escalates when the previous layer is insufficient.

This design borrows the useful general pattern of hierarchical retrieval while keeping Project Memory focused on project continuity.

## Why source hydration is narrow

Structural context is often enough to locate the correct code area, but some tasks require exact implementation evidence.

Instead of loading entire files, GPM can hydrate small source spans derived from validated Graphify locations.

This preserves:

- evidence quality;
- traceability;
- lower context volume;
- separation of responsibilities.

GPM does not build its own AST to accomplish this.

## Why durable facts need identity and lifecycle

A project memory that only appends prose eventually becomes contradictory.

For example, a durable fact may change over time:

```text
service A → uses backend X
```

later becomes:

```text
service A → uses backend Y
```

Simply keeping both as equally active statements is unsafe.

GPM therefore gives durable facts canonical identity and lifecycle states.

A new value for the same subject/predicate can supersede the previous active value while preserving history.

This provides auditability without pretending that old information never existed.

## Why provenance is required

Memory without provenance is difficult to trust.

A durable assertion should be able to point back toward its evidence.

GPM supports provenance fields such as:

```text
path
source_label
line_start
line_end
source_revision
observed_at
confidence
```

This makes the chain reversible:

```text
memory assertion
      ↓
Graphify relationship
      ↓
source evidence
```

The goal is not merely to remember an answer, but to preserve enough information to verify it later.

## Why freshness is content-based

Git HEAD alone is not enough to determine whether project source changed.

A commit may modify:

- Project Memory metadata;
- Graphify artifacts;
- generated reports;
- agent instructions managed by GPM.

Treating every HEAD advance as a source change would create false stale states.

GPM therefore distinguishes:

- `source_revision`;
- `observed_head`;
- source-content fingerprint;
- graph drift.

This allows metadata-only commits to advance Git history while preserving source freshness.

## Why the managed AGENTS.md block is normalized

GPM can maintain a marked section inside `AGENTS.md`.

If every change to that generated section counted as a source change, Project Memory could invalidate its own freshness baseline merely by maintaining its instructions.

The managed block is therefore normalized for source fingerprinting.

Human edits outside that block remain significant.

This creates a clean ownership boundary between generated instructions and human-authored project guidance.

## Why validation is conservative

GPM does not attempt to infer semantic truth from every code change.

If a fact's evidence disappears or its supporting revision changes, the safe response is not to guess.

The fact can be marked:

```text
needs_validation
```

and retrieval can escalate to Graphify or source evidence.

This is a deliberate design choice:

> uncertainty should be visible rather than silently converted into confidence.

## Why there is no mandatory daemon

Continuous background maintenance adds complexity and creates another system that can fail independently.

Graphify already provides code watching where needed:

```text
graphify watch .
```

Project Memory itself benefits from deliberate updates at meaningful operational boundaries:

- after a validated change;
- when a durable decision is made;
- when an issue is discovered;
- at a checkpoint;
- when ending a work session.

This produces a cleaner memory than recording every transient action.

## Why there is no vector database

Vector search can be useful in many systems, but it was not necessary for the core problem GPM addresses.

The existing stack already provides:

- structured operational memory;
- graph-based structural retrieval;
- exact source hydration;
- Git history.

Adding embeddings or a vector database would introduce additional storage, synchronization, dependencies, and retrieval behavior without being required for the current architecture.

The design remains open to future experimentation, but vector infrastructure is not part of the core system.

## Why consolidation does not delete history

Operational memory needs both:

- a compact current view;
- an auditable raw history.

`gpm consolidate` can produce a compact summary from active facts, decisions, and checkpoints while preserving original durable records.

This separates retrieval optimization from historical deletion.

## Why context metrics are estimates

GPM can compare retrieved context against broader corpus baselines and estimate avoided context.

These metrics are useful for evaluating retrieval quality.

However, provider billing depends on external model and API behavior.

For that reason, metrics are described as:

```text
context_avoided_estimate
context_reduction_percent
```

rather than guaranteed monetary or billed-token savings.

## What influenced the design

The architecture was informed by patterns found across adjacent memory and retrieval systems:

- progressive recall;
- hierarchical retrieval;
- reversible evidence chains;
- durable shared knowledge;
- revocation and supersession;
- provenance;
- separation of fast retrieval from slower maintenance.

The project intentionally adopts only the patterns that strengthen operational continuity.

It does not attempt to reproduce the full architecture of those systems.

## Final design rule

Graphify Project Memory follows one constraint above all others:

> Add only the memory and retrieval capabilities that are missing between Git, Graphify, and source code.

That constraint keeps the project understandable, testable, and auditable while still solving the continuity problem it was created for.
