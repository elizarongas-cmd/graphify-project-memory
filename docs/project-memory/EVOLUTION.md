# Project Memory Evolution

This file records material technical changes, compatibility decisions, regression contracts, and validation milestones for Graphify Project Memory.

It is intended to remain public and versionable.

It should not contain private project names, local development paths, credentials, personal operational memory, or internal planning notes that do not describe shipped behavior.

For the current architecture and design principles, see:

```text
docs/ARCHITECTURE.md
docs/DESIGN_RATIONALE.md
```

---

## 2026-09-11 — Project Memory 0.3.0

### Initial adaptive continuity layer

Project Memory 0.3.0 established the first complete operational-memory workflow around Graphify and Git.

Implemented:

- Idempotent migration from schema 1 to schema 2.
- Existing project state, decisions, issues, metrics, and checkpoints are preserved during migration.
- Added `source-reads.jsonl`.
- Added `gpm query --adaptive`.
- Adaptive queries start with compact Project Memory.
- Structural questions or insufficient memory can escalate to Graphify.
- Graphify query budget expands when results report truncation.
- Added task-scoped retrieval metrics through `task_id`.
- Added `gpm source-add` for verified source reads.
- Added:
  - `gpm report --task`
  - `gpm report --all`
- Checkpoints began including active-task retrieval reporting.
- The installer began maintaining the GPM-managed section of `AGENTS.md` idempotently.
- Added support for creating a local Graphify graph in code-only mode when no semantic provider is available.
- Added compatibility with either a globally installed Graphify CLI or an isolated Graphify runtime.

### Architectural boundary

The initial architecture established the responsibility split that remains in place:

- Git owns source history and recovery.
- Graphify owns derived structural knowledge.
- Project Memory owns operational continuity.
- Source code remains the final evidence layer.

### Validation

Initial automated validation:

```text
10 tests passed
```

---

## 2026-09-11 — Project Memory 0.3.1

### Hardening of the 0.3 architecture

0.3.1 focused on correctness, observability, privacy, and compatibility rather than adding a new memory architecture.

### Git and sharing policy

Fixed a contradictory early Git policy.

Durable Project Memory state may be shareable/versionable, while local telemetry remains local by default.

Portable Graphify artifacts may also be shareable, while local/regenerable artifacts remain excluded.

The policy distinguishes:

Shareable durable state:

```text
.project-memory/config.json
.project-memory/state.json
.project-memory/work-items.json
.project-memory/issues.json
.project-memory/decisions.jsonl
.project-memory/checkpoints.jsonl
```

Local telemetry:

```text
.project-memory/metrics.jsonl
.project-memory/source-reads.jsonl
```

Portable Graphify artifacts:

```text
graphify-out/graph.json
graphify-out/manifest.json
graphify-out/GRAPH_REPORT.md
```

Local/regenerable Graphify artifacts remain excluded.

### Schema and freshness

- Migrated to schema version 3.
- Added `graph-state.json`.
- Added a persistent Git ↔ Graphify baseline.
- Added `gpm freshness`.
- Freshness reports explicit reasons for drift rather than pretending to infer semantic truth.

### Graphify capability probing

Earlier code assumed some Graphify features were always present.

0.3.1 changed that model:

- Graphify capabilities are probed at runtime.
- Optional capabilities can degrade gracefully.
- The installed interface is trusted more than a hard-coded version assumption.

### Adaptive retrieval telemetry

Added explicit retrieval diagnostics:

```text
memory_coverage
coverage_threshold
escalation_reason
```

Structural questions still escalate automatically.

Graphify budget expansion remains available when traversal is truncated.

### Metrics terminology

The earlier `saved_tokens` label could be confused with provider-billed token savings.

The primary terminology became:

```text
context_avoided_estimate
context_reduction_percent
```

Legacy fields were temporarily retained for compatibility.

These metrics describe local context reduction, not guaranteed billing savings.

### Provenance

New durable decisions and issues began recording minimal provenance:

```text
task_id
source
git_head
```

### Source-read privacy guard

`gpm source-add` gained two important behaviors:

- deduplicate the same path within a task;
- refuse obvious secret/key paths unless explicitly overridden.

This created an early privacy boundary before source hydration existed.

### Documentation synchronization

The schema and public documentation were brought back in sync with the actual implementation.

### Deliberately deferred

Automatic source hydration was not implemented yet because a stable Graphify output contract had not been validated across supported interfaces.

The rule established here was:

> do not build fragile parsing around an assumed Graphify output shape.

---

## 2026-09-11 — Project Memory 0.3.2

### Graphify 0.9.57 query-budget compatibility fix

0.3.2 fixed a capability-detection false negative.

Graphify 0.9.57 could interpret:

```text
graphify query --help
```

as a literal query rather than returning subcommand help.

Therefore, help-text inspection could incorrectly conclude that query budgets were unsupported.

The capability probe was replaced with a real sentinel query.

Effects:

- `query_budget` detection became behavior-based.
- No schema change was required.
- Existing memory remained compatible.
- A dedicated regression test was added.

Validation suite:

```text
13 tests passed
```

---

## 2026-09-11 — Project Memory 0.3.3

### Content-based working-tree fingerprinting

Freshness moved beyond relying on raw `git status` text.

Implemented:

- fingerprint relevant working-tree file contents;
- record source-significant content state;
- older baselines without a content fingerprint intentionally report:

```text
working_tree_fingerprint_missing
```

until a new baseline/checkpoint is captured.

### Graphify source hygiene

`gpm install` began maintaining `.graphifyignore`.

Default ignored areas include:

```text
.project-memory/
graphify-out/
.git/
Python caches
package metadata
```

This prevents Project Memory's own operational artifacts from expanding Graphify's project graph.

---

## 2026-09-11 — Project Memory 0.3.4

### Source freshness vs derived graph drift

0.3.4 formalized an important distinction:

> source freshness is authoritative; derived Graphify drift is diagnostic.

Previously, raw changes in `graph.json` or `manifest.json` could make a project appear stale even when the source was unchanged.

Changed behavior:

- Source fingerprint drives freshness.
- Raw Graphify graph/manifest changes with identical source produce a warning, not source stale.
- Working-tree fingerprint records `content_file_count`.
- When Git cannot enumerate useful project paths, GPM uses a conservative filesystem fallback.

The fallback excludes:

```text
.git/
.project-memory/
graphify-out/
caches
build outputs
```

This protects freshness from generated or derived artifacts.

### Design consequence

The release established that Graphify outputs may vary independently from source truth.

Project Memory therefore records graph drift without allowing it to overwrite source authority.

---

## 2026-09-11 — Project Memory 0.3.5

### Consolidation of the operational-memory lifecycle

0.3.5 implemented several capabilities that had previously been deliberately deferred until real Graphify behavior and project usage were better understood.

### Schema v4

- Migrated schema 3 projects to schema 4.
- Migration preserves durable history.
- Added:

```text
facts.jsonl
```

### Source revision vs observed HEAD

Freshness now distinguishes:

```text
source_revision
observed_head
```

`source_revision` represents the source revision captured by the baseline.

`observed_head` represents the Git HEAD observed at capture time.

This prevents metadata-only commits from falsely advancing source truth.

### Metadata-only commit behavior

A metadata-only commit may advance Git HEAD while source remains fresh.

This avoids a checkpoint → commit → stale → checkpoint loop.

That loop is explicitly considered a regression failure.

### Durable fact identity

Added canonical durable facts.

A fact has deterministic identity based on canonical:

```text
subject
predicate
value
```

Lifecycle states:

```text
active
superseded
revoked
stale
needs_validation
```

Changing the value for the same subject/predicate supersedes the previous active fact while preserving history.

### Auditable fact lifecycle

The following behaviors became acceptance requirements:

- supersession remains visible;
- revocation remains visible;
- historical facts are not silently deleted;
- stale or missing evidence does not silently remain trusted.

### Provenance

Durable facts, decisions, and issues can carry stronger evidence metadata:

```text
source_type
path
source_label
line_start
line_end
source_revision
observed_at
```

### Conservative conflict validation

Added:

```text
gpm validate-facts
```

A source-backed fact may become:

```text
needs_validation
```

when:

- the evidence file disappears;
- the supporting source revision advances;
- the evidence can no longer be trusted without revalidation.

The system does not guess whether the fact became true or false.

### Adaptive escalation from fact health

If a query retrieves facts that require validation, adaptive retrieval may escalate to Graphify rather than silently trusting them.

### Hierarchical retrieval

0.3.5 completed the retrieval chain:

```text
Project Memory
      ↓
Graphify
      ↓
narrow source hydration
```

This realizes the earlier "map first, source later" design without introducing a second AST.

### Source hydration

Added measured narrow source hydration from validated Graphify source-location output.

Hydration is intentionally bounded by:

- number of files;
- source-range radius;
- token budget.

The default behavior avoids loading entire repositories.

### Consolidation

Added:

```text
gpm consolidate
```

Consolidation creates a compact current summary from:

- active facts;
- active/recent decisions;
- recent checkpoints.

Raw durable history remains preserved.

### Checkpoint behavior

Checkpoints now:

- validate facts;
- consolidate memory;
- capture source state;
- capture graph state.

With:

```text
--no-graphify
```

the checkpoint skips rerunning Graphify but still captures the currently available source/graph baseline.

### Doctor diagnostics

`gpm doctor` gained durable-fact health visibility.

### Artifact hygiene

`gpm install` began excluding local/regenerable Graphify artifacts by default:

```text
runtime/
cache/
memory/
reflections/
graph.html
.vocab.txt
dated backups
pre-Graphify snapshots
```

Portable artifacts remain shareable by policy:

```text
graph.json
manifest.json
GRAPH_REPORT.md
```

### Retrieval telemetry

Reports gained additional visibility into:

- memory candidates;
- selected memory;
- source hydration;
- fact-validation state.

### 0.3 branch acceptance gates

The stabilization branch established explicit regression gates:

1. Schema migration must preserve durable history.
2. `gpm install` must not modify functional project source.
3. A real source change must produce stale freshness.
4. Restoring source must restore freshness.
5. Graphify-only drift must remain a warning, not source stale.
6. Metadata/checkpoint commits must not create an infinite freshness loop.
7. Adaptive queries must begin with compact memory.
8. Structural questions must escalate to Graphify.
9. Source hydration must remain narrow and bounded.
10. Fact supersession and revocation must remain auditable.
11. Missing or stale evidence must produce `needs_validation` rather than silent trust.

### Deliberate non-goals

Still intentionally outside the architecture:

- custom MCP duplicating Graphify;
- a second AST;
- a second knowledge graph;
- mandatory embeddings/vector database;
- mandatory background consolidation daemon;
- autonomous multi-agent orchestration.

### Validation

Validation expanded from earlier suites to:

```text
25 tests passed
```

before stabilization packaging.

---

## 2026-09-11 — Project Memory 0.3.6

### Fingerprint v2 stabilization

0.3.6 is intentionally a stabilization release.

It does not introduce a new memory architecture.

Added explicit fingerprint versioning:

```text
source_fingerprint_version: 2
```

### Managed AGENTS.md block

The GPM-managed block inside root `AGENTS.md` is source-neutral for fingerprinting.

Only the marked GPM-owned section is normalized.

Human-authored edits outside that managed block remain source-significant.

This preserves both:

- safe GPM instruction maintenance;
- meaningful freshness for human project guidance.

### Conservative legacy fingerprint migration

A legacy fingerprint can migrate to v2 only when GPM can prove all of the following:

1. a valid `source_revision` exists;
2. intervening Git commits contain no source-significant changes;
3. the normalized working tree is source-clean.

If those conditions cannot be proven, automatic rebaselining is refused.

This prevents migration from silently hiding real source changes.

### Windows newline normalization

LF/CRLF differences in `AGENTS.md` are normalized before managed-block comparison.

This prevents false `source_dirty` results caused only by Windows newline translation.

### Git porcelain parsing fix

Parsing of:

```text
git status --porcelain
```

was corrected so the leading status column is preserved.

This prevents false dirty-state classification.

### Safe AGENTS.md ownership

`gpm install` updates only its managed block.

It must preserve surrounding human-authored `AGENTS.md` content.

The safe update workflow therefore does not overwrite the full destination file.

### Fact provenance stabilization

`fact-add` now records:

```text
effective_source_revision
```

instead of blindly using current observed HEAD.

This keeps metadata-only commits from rewriting source provenance.

### Fact reassertion

Reasserting the same canonical fact:

- preserves the fact ID;
- does not create a duplicate identity;
- may refresh provenance;
- records a `reassert` event.

### 0.3.6 regression contract

The following behaviors are explicitly protected:

1. GPM-managed `AGENTS.md` block changes only → source remains fresh.
2. Human `AGENTS.md` edits outside the block → source becomes stale.
3. Metadata-only commit → `source_revision` remains stable.
4. Real source commit → freshness becomes stale.
5. Legacy fingerprint migration refuses to rebaseline when source changed.
6. LF/CRLF normalization must not create false dirty state.
7. Fact provenance must point to the effective source revision.
8. Reasserting the same fact must preserve canonical identity.

### Final validation

The release was validated across:

- source fingerprinting;
- metadata-only commits;
- real source changes;
- source restoration;
- Graphify integration;
- adaptive retrieval;
- narrow source hydration;
- durable facts;
- provenance;
- fact validation;
- conflict handling;
- operational state;
- checkpoints;
- continuity recovery;
- retrieval metrics;
- Graphify watch compatibility.

Final automated validation:

```text
32 tests passed
```

---

## Design patterns incorporated over the 0.3 series

Several patterns were intentionally adopted only after they proved useful for the project's specific continuity problem.

### Progressive recall

Retrieve in increasing cost/order of specificity:

```text
compact operational memory
→ structural graph
→ exact source evidence
```

### Reversible evidence chain

Durable information should be traceable back toward evidence:

```text
summary
→ memory record
→ Graphify relationship
→ source range
```

### Canonical durable facts

A durable fact should have one canonical identity with visible lifecycle transitions rather than accumulating contradictory prose.

### Temporal validity and supersession

Facts may stop being current without being erased from history.

### Fast retrieval vs slower maintenance

Interactive queries stay small.

Consolidation, validation, and checkpoint maintenance occur at deliberate boundaries instead of every file write.

### Capability probing

Graphify integration is behavior/capability based where possible rather than tightly coupled to one CLI version.

---

## Stable responsibility boundary

Across all 0.3 releases, the core boundary remains unchanged:

### Git

Owns:

- source history;
- commits;
- diffs;
- rollback and recovery.

### Graphify

Owns:

- derived code/document structure;
- graph relationships;
- traversal;
- structural queries;
- Graphify Work Memory and reflections.

### Project Memory

Owns:

- operational continuity;
- task state;
- durable facts;
- decisions;
- issues;
- checkpoints;
- provenance;
- freshness;
- adaptive context planning;
- retrieval metrics.

### Source code

Remains the final evidence when direct implementation verification is required.

---

## Public documentation

The current architecture and reasoning are documented in:

```text
docs/ARCHITECTURE.md
docs/DESIGN_RATIONALE.md
```

This evolution file should record shipped behavior, regression contracts, and validation milestones.

Internal planning history and private project memory should remain outside the public repository.
