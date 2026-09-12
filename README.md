# Graphify Project Memory 0.3.6

Graphify Project Memory is a zero-runtime-dependency companion for Graphify that keeps auditable project continuity while Graphify maps structural relationships and Git preserves source history.

## Authority boundaries

- **Git:** source history, reviewable changes and recovery.
- **Graphify:** derived code/document graph, structural queries, Work Memory and reflections.
- **Project Memory:** operational continuity, durable facts, decisions/issues/checkpoints, provenance, adaptive context planning, source hydration and retrieval metrics.

Project Memory does **not** implement its own AST, second knowledge graph, vector database, embeddings, daemon, duplicated MCP server or multi-agent framework.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system boundaries, retrieval flow, freshness and fact lifecycle.
- [`docs/DESIGN_RATIONALE.md`](docs/DESIGN_RATIONALE.md) — why the project uses these boundaries and deliberately avoids duplicate infrastructure.
- [`docs/project-memory/EVOLUTION.md`](docs/project-memory/EVOLUTION.md) — shipped technical evolution and regression contracts.
- [`MANUAL_G_P_M_0.3.6_PUBLIC.md`](MANUAL_G_P_M_0.3.6_PUBLIC.md) — practical Windows-oriented operating manual.
- [`SECURITY.md`](SECURITY.md) — responsible vulnerability reporting and secret-handling guidance.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development and contribution workflow.

## What is new in 0.3.6

0.3.6 is a stabilization release over 0.3.5. It fixes source-fingerprint false positives caused by GPM-managed metadata while preserving the 0.3 architecture.

- The `<!-- project-memory:start --> ... <!-- project-memory:end -->` block in root `AGENTS.md` is source-neutral for fingerprinting and dirty-state classification.
- Human edits outside that managed block remain source-significant and correctly make freshness stale.
- Legacy fingerprint baselines can migrate conservatively to fingerprint v2 when GPM proves that intervening commits are metadata-only and the source working tree is clean.
- Git porcelain parsing now preserves its leading status column, preventing false dirty classifications.

### Schema v4

Existing schema 3 projects migrate automatically to schema 4 without deleting state, work items, issues, decisions, checkpoints or telemetry. Schema v4 adds `facts.jsonl` and upgrades `graph-state.json` semantics.

### Source revision vs observed HEAD

Freshness no longer assumes every Git HEAD change is a source change.

- `source_revision`: last source revision represented by the baseline.
- Fact provenance records the effective source revision; metadata-only HEAD advances do not rewrite source truth. Reasserting the same fact can refresh provenance while preserving its fact ID.
- `observed_head`: Git HEAD seen at capture time.
- `source_content_sha256`: authoritative fingerprint of relevant source/project files.

A metadata-only commit that changes `.project-memory/` or `graphify-out/` can therefore change HEAD while source remains fresh.

### Durable fact lifecycle

Operational facts have canonical identity and lifecycle states:

```text
active
superseded
revoked
stale
needs_validation
```

Adding a new value for the same canonical `subject + predicate` supersedes the previous active value while preserving history.

### Provenance

Durable facts, decisions and issues can carry:

```text
source_type
path / source_label
line_start
line_end
source_revision
observed_at
```

This supports a reversible chain from memory to evidence without copying structural-code ownership away from Graphify.

### Conflict validation

`gpm validate-facts` marks source-backed facts `needs_validation` when their evidence file disappears or the source revision advances. Queries that retrieve a `needs_validation` fact escalate to Graphify instead of silently trusting stale memory.

### Hierarchical retrieval and source hydration

Adaptive retrieval now follows:

```text
compact Project Memory
        ↓
Graphify structural skeleton
        ↓
narrow source ranges
```

When Graphify is needed, 0.3.6 can hydrate a small number of exact source ranges from Graphify `src=... loc=L...` results. It never builds its own AST and never loads the entire repository by default.

### Consolidation

`gpm consolidate` writes `.project-memory/summaries/consolidated.md` from active facts, recent active decisions and recent checkpoints while preserving all raw durable history.

### Artifact hygiene

`gpm install` keeps portable Graphify artifacts shareable while excluding local/regenerable material such as runtime, cache, personal Work Memory, reflections, graph HTML, vocabulary and backup snapshots.

## Quick start

```text
python -m pip install -e .
gpm install --project C:\path\to\project
gpm doctor --project C:\path\to\project
gpm freshness --project C:\path\to\project
```

For a project already using 0.3.x, `gpm install --project .` performs the schema migration idempotently.

## Operational memory

```text
gpm status --project .
gpm state --current-task "..." --next-action "..." --project .
gpm work-add "..." --project .
gpm decision "..." --reason "..." --source src\module.py --start-line 10 --end-line 30 --project .
gpm issue "..." --source src\module.py --project .
```

## Durable facts

```text
gpm fact-add "audio_queue" "mode" "FIFO persistent" --source src\audio\audio_queue_service.py --start-line 15 --end-line 93 --project .
gpm facts --status active --project .
gpm fact-status FACT-XXXXXXXXXXXX revoked --reason "superseded by verified implementation" --project .
gpm validate-facts --project .
gpm consolidate --project .
```

Fact identity is deterministic from canonical subject/predicate/value. Reasserting the same fact is deduplicated; asserting a different value for the same subject/predicate supersedes the prior active fact.

## Adaptive retrieval

```text
gpm query "what should I do next" --adaptive --project .
gpm query "which functions participate in the audio queue" --adaptive --project .
```

Adaptive retrieval starts with compact Project Memory. It escalates when the question is structural, memory is empty/low coverage, or retrieved facts need validation. Graphify truncation can trigger a larger graph budget. By default, graph-backed adaptive queries hydrate a small source window; disable with `--no-hydrate`.

Hydration controls:

```text
--hydrate-files 3
--hydrate-radius 10
--hydrate-max-tokens 900
```

Automatically hydrated source ranges are logged as local `source-reads.jsonl` telemetry and are deduplicated per task/path/range.

## Freshness semantics

`gpm freshness` separates source truth from derived artifacts.

```text
HEAD changed + source fingerprint changed
→ stale

HEAD changed + source fingerprint identical
→ fresh + git_head_changed_without_source_change warning

graph/manifest changed + source identical
→ fresh + graph drift warning
```

Graph drift is diagnostic because Graphify output can vary independently of authoritative source content.

## Checkpoints

```text
gpm checkpoint "summary" --project .
```

A normal checkpoint updates/diagnoses Graphify, captures graph/source state, validates durable facts, consolidates memory and appends a checkpoint. It never creates a Git commit.

If Graphify was already updated explicitly:

```text
graphify update .
gpm checkpoint "summary" --no-graphify --project .
```

`--no-graphify` still captures the current graph/source baseline; it only avoids re-running Graphify.

## Shared vs local state

Shareable Project Memory:

```text
.project-memory/config.json
.project-memory/state.json
.project-memory/work-items.json
.project-memory/issues.json
.project-memory/decisions.jsonl
.project-memory/checkpoints.jsonl
.project-memory/facts.jsonl
.project-memory/baseline.json
.project-memory/graph-state.json
.project-memory/summaries/
```

Local telemetry:

```text
.project-memory/metrics.jsonl
.project-memory/source-reads.jsonl
```

Recommended shareable Graphify artifacts:

```text
graphify-out/graph.json
graphify-out/manifest.json
graphify-out/GRAPH_REPORT.md
```

Local/regenerable Graphify artifacts are ignored by `gpm install`, including `runtime/`, cache, memory, reflections, `graph.html`, `.vocab.txt`, dated backups and pre-Graphify snapshots.

## Metrics

Primary metrics remain estimates of context retrieval, not billing claims:

```text
context_avoided_estimate
context_reduction_percent
```

0.3.6 additionally records memory candidates/selection, source hydration files/ranges and queries involving facts that need validation.
