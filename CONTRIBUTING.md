# Contributing to Graphify Project Memory

Thank you for considering a contribution.

Graphify Project Memory is intentionally small and conservative. Contributions should strengthen operational continuity without duplicating responsibilities already owned by Git, Graphify, or source code.

## Design boundaries

Before proposing a substantial change, read:

- `docs/ARCHITECTURE.md`
- `docs/DESIGN_RATIONALE.md`
- `docs/project-memory/EVOLUTION.md`

The core responsibility split is:

- **Git:** source history, diffs, recovery and reviewable commits.
- **Graphify:** derived project structure, relationships, traversal and structural queries.
- **Project Memory:** operational state, facts, decisions, issues, checkpoints, provenance, freshness and adaptive context planning.
- **Source code:** final evidence.

The project deliberately avoids adding a second AST, second knowledge graph, mandatory vector database, duplicate MCP server, mandatory daemon, or autonomous multi-agent framework unless the architecture is intentionally reconsidered through a documented design change.

## Development setup

Requirements:

- Python 3.10 or newer;
- Git;
- Graphify for integration testing of Graphify-backed features.

Create a local environment and install the package in editable mode:

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e .
```

On POSIX shells the activation command is typically:

```text
source .venv/bin/activate
```

## Running tests

The repository uses Python's test tooling and currently maintains a regression suite under `tests/`.

Run:

```text
python -m pytest -q
```

If `pytest` is not already available in your development environment, install it locally as a development tool:

```text
python -m pip install pytest
```

Before submitting a change, ensure the full suite passes.

## Testing Graphify integration

Changes involving Graphify should be tested against the real installed CLI behavior when practical.

Useful checks include:

```text
graphify --help
graphify update .
graphify check-update .
```

For watcher behavior:

```text
graphify watch .
```

Do not hard-code assumptions from help text when a behavior-based capability probe is safer. Existing compatibility logic intentionally prefers real capability detection in several places.

## Regression expectations

Changes should preserve the established contracts unless the change explicitly and intentionally revises them.

Important contracts include:

1. `gpm install` must preserve functional project source.
2. Managed Project Memory metadata must not create false source drift.
3. Human edits outside the managed `AGENTS.md` block remain source-significant.
4. Metadata-only Git commits must not falsely advance `source_revision`.
5. Real source changes must make freshness stale.
6. Restoring source should restore freshness when no other source-significant change exists.
7. Graphify-only artifact drift is diagnostic, not authoritative source drift.
8. Adaptive retrieval starts from compact memory and escalates when required.
9. Source hydration remains narrow and bounded.
10. Durable fact supersession and revocation remain auditable.
11. Missing or stale fact evidence should result in `needs_validation`, not silent trust.
12. Reasserting the same canonical fact preserves its identity.

See `docs/project-memory/EVOLUTION.md` for the detailed evolution of these contracts.

## Adding or changing facts/provenance behavior

Changes to durable facts should preserve:

- deterministic canonical identity;
- lifecycle history;
- provenance;
- conservative validation;
- reversibility from memory toward source evidence.

Avoid deleting historical records merely to simplify current-state retrieval. Prefer consolidation for compact retrieval while keeping durable history auditable.

## Documentation changes

Public documentation should use generic project names and paths.

Prefer examples such as:

```text
C:\Projects\example-project
src\audio\audio_queue_service.py
```

Do not publish private project names, internal customer names, credentials, real `.project-memory` contents, or machine-specific paths that are not necessary to explain the feature.

Material behavior changes should update, when relevant:

- `README.md`;
- `MANUAL_G_P_M_0.3.6_PUBLIC.md` or its successor;
- `docs/ARCHITECTURE.md` for architecture changes;
- `docs/DESIGN_RATIONALE.md` for design-boundary changes;
- `docs/project-memory/EVOLUTION.md` for shipped behavior and regression contracts.

## Code style

Keep changes focused and readable.

Prefer:

- standard-library solutions when sufficient;
- small modules with clear ownership;
- explicit error handling;
- deterministic behavior for durable state;
- backward-compatible migrations when practical;
- tests for bug fixes and regression-sensitive behavior.

Avoid unrelated refactors in the same pull request as a functional fix.

## Commits and pull requests

A useful pull request should explain:

- the problem being solved;
- why the change belongs in Project Memory rather than Git or Graphify;
- the implementation approach;
- tests added or updated;
- compatibility or migration impact;
- documentation changes.

Do not include generated `.project-memory/`, `graphify-out/`, caches, build outputs, secrets, or private project artifacts.

## Versioning and compatibility

Do not change the package version merely for a local experiment.

A release version change should correspond to an intentional release decision and should remain consistent across:

- `pyproject.toml`;
- `src/graphify_project_memory/__init__.py`;
- `.codex-plugin/plugin.json`;
- public release documentation.

Schema migrations must preserve durable history unless a breaking migration is explicitly documented.

## Security

Read `SECURITY.md` before contributing changes involving file access, provenance, secret handling, hydration, subprocesses, or external-tool integration.

Do not place real secrets in tests. Use synthetic values only.
