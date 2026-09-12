# Security Policy

## Supported version

Graphify Project Memory is currently maintained on the latest published release in the `0.3.x` line. Security fixes should target the current release unless a maintainer explicitly announces broader support.

## Reporting a vulnerability

Please do **not** open a public GitHub issue for a vulnerability that could expose credentials, private project memory, local files, arbitrary code execution, or another user's data.

Use GitHub's private vulnerability reporting feature when it is enabled for the repository. If private reporting is not available, contact the maintainer through the contact method published in the repository metadata and clearly mark the message as a security report.

A useful report should include, when possible:

- affected Graphify Project Memory version;
- operating system and Python version;
- Graphify version, when the issue involves Graphify integration;
- minimal reproduction steps;
- expected behavior and observed behavior;
- security impact;
- a minimal proof of concept that does not contain real secrets or private project data.

Do not include production credentials, private repositories, personal data, audio files, model files, databases, or complete `.project-memory` directories in a report. Replace sensitive values with synthetic examples.

## Secrets and sensitive paths

Project Memory can record provenance and source-read information. Contributors should treat project paths and operational memory as potentially sensitive.

The public repository must not contain:

- API keys, access tokens, passwords, private keys, or session cookies;
- `.env` files containing real values;
- private `.project-memory` state from real projects;
- generated `graphify-out` Work Memory, reflections, caches, or private query history;
- private project names or local development paths when a generic example is sufficient;
- personal or customer datasets.

If a secret is committed accidentally, removing it from the latest file is not enough. Rotate or revoke the credential and clean the Git history before publication when appropriate.

## Security-relevant project boundaries

Graphify Project Memory deliberately relies on clear ownership boundaries:

- **Git** is the authority for source history and recovery.
- **Graphify** owns derived structural analysis and graph traversal.
- **Project Memory** owns operational continuity, durable facts, decisions, issues, checkpoints, provenance, and retrieval planning.
- **Source code** remains the final evidence layer.

Security fixes should preserve those boundaries. Avoid introducing duplicate parsers, hidden background services, or additional stores merely to work around an integration issue.

## Source hydration and provenance

Source hydration should remain narrow and bounded. Changes affecting source reads should preserve:

- explicit file/range provenance;
- secret-path safeguards;
- bounded retrieval budgets;
- conservative behavior when evidence is missing or stale.

A fact whose evidence can no longer be trusted should become `needs_validation` rather than silently remaining authoritative.

## Dependency policy

The core package is intentionally designed with zero runtime Python dependencies. New runtime dependencies should be introduced only when there is a clear, reviewed need and when their security and maintenance implications are understood.

Build and development tools are not covered by the zero-runtime-dependency goal.

## Disclosure process

Maintainers should confirm receipt of a valid report, reproduce the issue, assess affected versions, prepare a fix and regression test, and coordinate disclosure after a patched release is available when feasible.

Security fixes should include automated regression coverage whenever the behavior can be tested safely.
