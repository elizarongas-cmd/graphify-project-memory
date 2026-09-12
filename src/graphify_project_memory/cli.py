from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import graphify_bridge
from .storage import (
    SCHEMA_VERSION, append_jsonl, atomic_json, initialize, load_json, memory_root,
    memory_coverage, query_memory_records, read_jsonl, require_memory, utc_now,
)
from .tokens import context_reduction, estimate_tokens
from .reporting import summarize
from .facts import add_fact, set_fact_status, current_facts, validate_facts, consolidate
from .hydration import hydrate_sources
from .freshness import capture_graph_state, evaluate_freshness, git_snapshot, upgrade_graph_state_fingerprint


def project_path(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_dir():
        raise argparse.ArgumentTypeError(f"Project directory does not exist: {path}")
    return path


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=True, indent=2))


def git_head(project: Path) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _provenance(project: Path, source: str = "", start_line: int | None = None, end_line: int | None = None) -> dict[str, Any]:
    snapshot = git_snapshot(project)
    source_revision = snapshot.get("observed_head")
    try:
        root = require_memory(project)
        freshness = evaluate_freshness(project, root)
        source_revision = (((freshness.get("current") or {}).get("git") or {}).get("effective_source_revision") or source_revision)
    except Exception:
        # Provenance recording should remain available even if freshness cannot be evaluated.
        pass
    provenance: dict[str, Any] = {
        "source_revision": source_revision,
        "observed_at": utc_now(),
    }
    if source:
        path = Path(source)
        if not path.is_absolute():
            path = project / path
        if path.exists():
            try:
                provenance["path"] = path.resolve().relative_to(project.resolve()).as_posix()
                provenance["source_type"] = "source_file"
            except ValueError:
                provenance["source_label"] = source
                provenance["source_type"] = "external_label"
        else:
            provenance["source_label"] = source
            provenance["source_type"] = "label"
    else:
        provenance["source_type"] = "project_state"
    if start_line is not None:
        provenance["line_start"] = max(1, int(start_line))
    if end_line is not None:
        provenance["line_end"] = max(int(end_line), int(start_line or 1))
    return provenance


def command_init(args: argparse.Namespace) -> None:
    root, created = initialize(args.project, args.name)
    print_json({"memory_root": str(root), "created": created, "schema_version": SCHEMA_VERSION})


def command_status(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    state = load_json(root / "state.json", {})
    work = load_json(root / "work-items.json", {"items": []})["items"]
    issues = load_json(root / "issues.json", {"items": []})["items"]
    print_json({
        "project": load_json(root / "config.json", {}).get("project_name"),
        "phase": state.get("phase"), "current_task": state.get("current_task"),
        "next_action": state.get("next_action"),
        "pending_work_items": sum(item.get("status") != "completed" for item in work),
        "open_issues": sum(item.get("status") == "open" for item in issues),
        "decisions": len(read_jsonl(root / "decisions.jsonl")),
        "checkpoints": len(read_jsonl(root / "checkpoints.jsonl")),
    })


def command_state(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    state = load_json(root / "state.json", {"schema_version": SCHEMA_VERSION})
    for argument, key in (("objective", "objective"), ("phase", "phase"), ("current_task", "current_task"), ("next_action", "next_action"), ("task_id", "active_task_id")):
        value = getattr(args, argument)
        if value is not None:
            state[key] = value
    state["updated_at"] = utc_now()
    atomic_json(root / "state.json", state)
    print_json(state)


def command_work_add(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    data = load_json(root / "work-items.json", {"schema_version": SCHEMA_VERSION, "items": []})
    record = {"id": f"WORK-{len(data['items'])+1:04d}", "title": args.title, "status": args.status, "kind": args.kind, "source": args.source, "created_at": utc_now(), "updated_at": utc_now()}
    data["items"].append(record)
    atomic_json(root / "work-items.json", data)
    print_json(record)


def command_work_update(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    data = load_json(root / "work-items.json", {"schema_version": SCHEMA_VERSION, "items": []})
    record = next((item for item in data["items"] if item.get("id") == args.id), None)
    if not record:
        raise RuntimeError(f"Work item not found: {args.id}")
    record["status"] = args.status
    record["updated_at"] = utc_now()
    atomic_json(root / "work-items.json", data)
    print_json(record)


STRUCTURAL_TERMS = {
    "code", "codigo", "funcion", "function", "class", "clase", "module", "modulo",
    "file", "archivo", "api", "call", "llama", "depende", "dependency", "route", "ruta",
    "implementa", "implementation", "relationship", "relacion",
}


def _graph_escalation_reason(question: str, memory_text: str, coverage: float, threshold: float = 0.5, needs_validation: bool = False) -> str | None:
    if needs_validation:
        return "memory_needs_validation"
    words = set(re.findall(r"[a-záéíóúñ_]+", question.lower()))
    if words & STRUCTURAL_TERMS:
        return "structural_question"
    if not memory_text.strip():
        return "memory_empty"
    if coverage < threshold:
        return "memory_coverage_low"
    return None


def _needs_graph(question: str, memory_text: str, coverage: float = 1.0, threshold: float = 0.5, needs_validation: bool = False) -> bool:
    return _graph_escalation_reason(question, memory_text, coverage, threshold, needs_validation) is not None


def command_query(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    config = load_json(root / "config.json", {})
    state = load_json(root / "state.json", {})
    budget = args.budget or int(config.get("query_budget", 600))
    task_id = args.task or state.get("active_task_id") or "unassigned"
    memory_records = query_memory_records(args.project, args.question, args.limit)
    memory_text = "\n".join(f"[{record['source']}] {record['text']}" for record in memory_records)
    coverage = memory_coverage(args.question, memory_records)
    memory_needs_validation = any(record.get("status") == "needs_validation" for record in memory_records)
    graph_text = ""
    graph_error = None
    expanded = False
    expansion_reason = ""
    tier = "memory"
    escalation_reason = None
    source_text = ""
    hydrated_ranges: list[dict[str, Any]] = []
    source_tokens = 0
    if args.adaptive:
        escalation_reason = _graph_escalation_reason(
            args.question, memory_text, coverage, args.coverage_threshold, memory_needs_validation
        )
    should_query_graph = not args.adaptive or escalation_reason is not None
    if should_query_graph:
        tier = "graph"
        initial_budget = min(budget, args.initial_budget) if args.adaptive else budget
        try:
            graph_text = graphify_bridge.query(args.project, args.question, initial_budget)
            if args.adaptive and "TRUNCATED" in graph_text.upper() and initial_budget < args.max_budget:
                expanded = True
                expansion_reason = "graph_truncated"
                tier = "graph_expanded"
                graph_text = graphify_bridge.query(args.project, args.question, args.max_budget)
            if args.adaptive and args.hydrate and graph_text:
                hydrated = hydrate_sources(
                    args.project, graph_text, limit=args.hydrate_files,
                    radius=args.hydrate_radius, max_tokens=args.hydrate_max_tokens,
                )
                source_text = hydrated["text"]
                hydrated_ranges = hydrated["ranges"]
                source_tokens = int(hydrated["tokens"])
                if hydrated_ranges:
                    tier = "source_hydrated"
                    existing = read_jsonl(root / "source-reads.jsonl")
                    seen = {(item.get("task_id"), item.get("path"), item.get("start_line"), item.get("end_line")) for item in existing}
                    revision = git_snapshot(args.project).get("observed_head")
                    for item in hydrated_ranges:
                        key = (task_id, item.get("path"), item.get("start_line"), item.get("end_line"))
                        if key not in seen:
                            append_jsonl(root / "source-reads.jsonl", {
                                "timestamp": utc_now(), "task_id": task_id, "path": item.get("path"),
                                "start_line": item.get("start_line"), "end_line": item.get("end_line"),
                                "tokens": item.get("tokens", 0), "git_head": revision,
                                "kind": "automatic_source_hydration",
                            })
                            seen.add(key)
        except Exception as error:
            graph_error = str(error)
    memory_tokens = estimate_tokens(memory_text)
    graph_tokens = estimate_tokens(graph_text)
    actual = memory_tokens + graph_tokens + source_tokens
    baseline = int(load_json(root / "baseline.json", {}).get("corpus_tokens") or actual)
    avoided, percent = context_reduction(baseline, actual)
    metric = {
        "timestamp": utc_now(), "task_id": task_id, "question": args.question,
        "baseline_tokens": baseline, "memory_tokens": memory_tokens,
        "graph_tokens": graph_tokens, "source_tokens": source_tokens,
        "total_retrieval_tokens": actual,
        "context_avoided_estimate": avoided, "context_reduction_percent": percent,
        "saved_tokens": avoided, "saving_percent": percent,
        "quality": args.quality, "adaptive": bool(args.adaptive), "context_tier": tier,
        "memory_coverage": coverage, "coverage_threshold": args.coverage_threshold,
        "memory_candidates": len(memory_records), "memory_selected": len(memory_records),
        "memory_needs_validation": memory_needs_validation,
        "escalation_reason": escalation_reason or "",
        "expanded": expanded, "expansion_reason": expansion_reason,
        "hydrated_files": len({item.get('path') for item in hydrated_ranges}),
        "hydrated_ranges": len(hydrated_ranges),
    }
    append_jsonl(root / "metrics.jsonl", metric)
    print_json({
        "memory": memory_text, "memory_records": memory_records, "memory_coverage": coverage,
        "graph": graph_text, "graph_error": graph_error,
        "source": source_text, "source_ranges": hydrated_ranges, "metric": metric,
    })


def command_decision(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    values = read_jsonl(root / "decisions.jsonl")
    state = load_json(root / "state.json", {})
    provenance = _provenance(args.project, args.source, getattr(args, "start_line", None), getattr(args, "end_line", None))
    record = {
        "id": f"DEC-{len(values)+1:04d}", "timestamp": utc_now(), "decision": args.text,
        "reason": args.reason, "status": "active",
        "task_id": args.task or state.get("active_task_id"), "source": args.source,
        "git_head": provenance.get("source_revision"), "provenance": provenance,
    }
    append_jsonl(root / "decisions.jsonl", record)
    print_json(record)


def command_issue(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    data = load_json(root / "issues.json", {"schema_version": SCHEMA_VERSION, "items": []})
    state = load_json(root / "state.json", {})
    provenance = _provenance(args.project, args.source, getattr(args, "start_line", None), getattr(args, "end_line", None))
    record = {
        "id": f"ISS-{len(data['items'])+1:04d}", "title": args.title, "details": args.details,
        "status": args.status, "created_at": utc_now(), "updated_at": utc_now(),
        "task_id": args.task or state.get("active_task_id"), "source": args.source,
        "git_head": provenance.get("source_revision"), "provenance": provenance,
    }
    data["items"].append(record)
    atomic_json(root / "issues.json", data)
    print_json(record)


def command_checkpoint(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    outputs: dict[str, str] = {}
    if not args.no_graphify:
        outputs = graphify_bridge.checkpoint(args.project, args.summary)
    graph_state = capture_graph_state(args.project, root, graphify_bridge.version(args.project))
    source_revision = (graph_state.get("git") or {}).get("source_revision")
    validation = validate_facts(root, args.project, source_revision)
    consolidation = consolidate(root)
    record = {
        "timestamp": utc_now(), "summary": args.summary,
        "git_head": (graph_state.get("git") or {}).get("observed_head"),
        "source_revision": source_revision,
        "graphify_synced": not args.no_graphify,
        "graph_state": graph_state,
        "fact_conflicts": len(validation.get("conflicts", [])),
    }
    append_jsonl(root / "checkpoints.jsonl", record)
    task_id = load_json(root / "state.json", {}).get("active_task_id")
    task_report = summarize(read_jsonl(root / "metrics.jsonl"), read_jsonl(root / "source-reads.jsonl"), task_id) if task_id else None
    print_json({
        "checkpoint": record, "graphify": outputs, "fact_validation": validation,
        "consolidation": consolidation, "task_report": task_report,
    })


def parse_benchmark(output: str) -> dict[str, Any]:
    corpus = re.search(r"~([\d,]+) tokens", output)
    average = re.search(r"Avg query cost:\s+~([\d,]+) tokens", output)
    reduction = re.search(r"Reduction:\s+([\d.]+)x", output)
    return {
        "corpus_tokens": int(corpus.group(1).replace(",", "")) if corpus else None,
        "average_graph_query_tokens": int(average.group(1).replace(",", "")) if average else None,
        "graph_reduction_x": float(reduction.group(1)) if reduction else None,
    }


def command_benchmark(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    config = load_json(root / "config.json", {})
    graph_path = args.project / config.get("graph_dir", "graphify-out") / "graph.json"
    output = graphify_bridge.benchmark(args.project, graph_path)
    result = {"schema_version": SCHEMA_VERSION, "captured": True, "captured_at": utc_now(), **parse_benchmark(output), "raw": output}
    atomic_json(root / "baseline.json", result)
    print_json(result)


def command_metrics(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    print_json(summarize(
        read_jsonl(root / "metrics.jsonl"),
        read_jsonl(root / "source-reads.jsonl"),
    ))


def command_source_add(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    project = args.project.resolve()
    state = load_json(root / "state.json", {})
    task_id = args.task or state.get("active_task_id") or "unassigned"
    records = []
    for value in args.paths:
        path = Path(value)
        if not path.is_absolute():
            path = project / path
        path = path.resolve()
        try:
            relative = path.relative_to(project)
        except ValueError as error:
            raise RuntimeError(f"Source is outside the project: {path}") from error
        if not path.is_file():
            raise RuntimeError(f"Source file does not exist: {path}")
        sensitive_names = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
        sensitive_suffixes = {".pem", ".key", ".p12", ".pfx"}
        if not args.allow_sensitive and (path.name.lower() in sensitive_names or path.suffix.lower() in sensitive_suffixes):
            raise RuntimeError(f"Refusing to record sensitive source path without --allow-sensitive: {relative.as_posix()}")
        content_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        start_line = max(1, int(getattr(args, "start_line", None) or 1))
        end_line = min(len(content_lines), int(getattr(args, "end_line", None) or len(content_lines)))
        selected = "\n".join(content_lines[start_line-1:end_line])
        record = {
            "timestamp": utc_now(), "task_id": task_id,
            "path": relative.as_posix(), "start_line": start_line, "end_line": end_line,
            "tokens": estimate_tokens(selected),
            "git_head": git_head(project), "kind": "verified_source_read",
        }
        existing = read_jsonl(root / "source-reads.jsonl")
        duplicate = any(item.get("task_id") == task_id and item.get("path") == record["path"] and item.get("start_line") == record["start_line"] and item.get("end_line") == record["end_line"] for item in existing)
        if not duplicate:
            append_jsonl(root / "source-reads.jsonl", record)
        record["duplicate"] = duplicate
        records.append(record)
    print_json({"task_id": task_id, "sources": records})


def command_fact_add(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    provenance = _provenance(args.project, args.source, getattr(args, "start_line", None), getattr(args, "end_line", None))
    record = add_fact(root, args.subject, args.predicate, args.value, provenance, args.confidence)
    print_json(record)


def command_fact_status(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    print_json(set_fact_status(root, args.id, args.status, args.reason))


def command_facts(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    values = current_facts(root)
    if args.status:
        values = [item for item in values if item.get("status") == args.status]
    print_json({"facts": values, "count": len(values)})


def command_validate_facts(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    freshness = evaluate_freshness(args.project, root)
    source_revision = ((freshness.get("current") or {}).get("git") or {}).get("effective_source_revision")
    print_json(validate_facts(root, args.project, source_revision))


def command_consolidate(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    print_json(consolidate(root))


def command_report(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    state = load_json(root / "state.json", {})
    task_id = None if args.all else (args.task or state.get("active_task_id"))
    print_json(summarize(
        read_jsonl(root / "metrics.jsonl"),
        read_jsonl(root / "source-reads.jsonl"),
        task_id,
    ))


def command_freshness(args: argparse.Namespace) -> None:
    root = require_memory(args.project)
    print_json(evaluate_freshness(args.project, root))


def command_doctor(args: argparse.Namespace) -> None:
    errors: list[str] = []
    warnings: list[str] = []
    root = memory_root(args.project)
    required = [
        "config.json", "state.json", "work-items.json", "issues.json", "baseline.json",
        "graph-state.json", "decisions.jsonl", "checkpoints.jsonl", "metrics.jsonl", "source-reads.jsonl", "facts.jsonl",
    ]
    for filename in required:
        if not (root / filename).exists():
            errors.append(f"missing {filename}")
    if (root / "config.json").exists() and load_json(root / "config.json", {}).get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema version")
    capabilities = graphify_bridge.capabilities(args.project)
    if not capabilities.get("available"):
        warnings.append("Graphify CLI is not available")
    graph = args.project / "graphify-out" / "graph.json"
    if not graph.exists():
        warnings.append("graphify-out/graph.json is missing")
    freshness = evaluate_freshness(args.project, root) if (root / "config.json").exists() else None
    if freshness and not freshness.get("fresh"):
        warnings.append("project source freshness baseline differs from current state")
    if freshness and freshness.get("warnings"):
        warnings.extend(f"freshness: {item}" for item in freshness["warnings"])
    facts = current_facts(root) if (root / "facts.jsonl").exists() else []
    fact_health = {
        "total": len(facts),
        "active": sum(item.get("status") == "active" for item in facts),
        "needs_validation": sum(item.get("status") == "needs_validation" for item in facts),
        "revoked": sum(item.get("status") == "revoked" for item in facts),
        "superseded": sum(item.get("status") == "superseded" for item in facts),
    }
    if fact_health["needs_validation"]:
        warnings.append(f"{fact_health['needs_validation']} fact(s) need validation")
    print_json({
        "ok": not errors, "errors": errors, "warnings": warnings, "memory_root": str(root),
        "graphify": capabilities, "freshness": freshness, "facts": fact_health,
    })
    if errors:
        raise SystemExit(1)


AGENTS_BLOCK = """
<!-- project-memory:start -->
## Project Memory

Start with `gpm status --project .` and `gpm freshness --project .`. Use `gpm query "<question>" --adaptive --project .` before broad reads: operational memory is compact-first, Graphify provides structural context, and source hydration reads only narrow verified ranges when needed. Durable operational facts belong in `gpm fact-add`; use lifecycle statuses instead of deleting history. Record exact source ranges when available. After material work, checkpoint once; use `--no-graphify` when Graphify was already updated explicitly. Never commit automatically without explicit user authorization and never treat estimated context reduction as provider-billed savings.
<!-- project-memory:end -->
"""


def ensure_line(path: Path, line: str) -> bool:
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = {value.strip() for value in content.splitlines()}
    if line in existing:
        return False
    separator = "" if not content or content.endswith("\n") else "\n"
    path.write_text(content + separator + line + "\n", encoding="utf-8")
    return True



def ensure_absent_line(path: Path, line: str) -> bool:
    if not path.exists():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [value for value in lines if value.strip() != line]
    if kept == lines:
        return False
    path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return True

def ensure_evolution(project: Path) -> tuple[Path, bool]:
    target = project / "docs" / "project-memory" / "EVOLUTION.md"
    if target.exists():
        return target, False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# Evolución del proyecto\n\n"
        "Registro versionado de cambios materiales, decisiones y verificaciones.\n",
        encoding="utf-8",
    )
    return target, True

def command_install(args: argparse.Namespace) -> None:
    memory, created = initialize(args.project, args.name)
    target = args.project / "AGENTS.md"
    content = target.read_text(encoding="utf-8") if target.exists() else ""
    start = "<!-- project-memory:start -->"
    end = "<!-- project-memory:end -->"
    if start in content and end in content:
        before, remainder = content.split(start, 1)
        _, after = remainder.split(end, 1)
        updated = before + AGENTS_BLOCK.strip() + after
        changed = updated != content
        if changed:
            target.write_text(updated, encoding="utf-8")
    else:
        target.write_text(content.rstrip() + "\n" + AGENTS_BLOCK, encoding="utf-8")
        changed = True
    evolution, evolution_created = ensure_evolution(args.project)
    gitignore = args.project / ".gitignore"
    removed_blanket_graph = ensure_absent_line(gitignore, "graphify-out/")
    removed_blanket_memory = ensure_absent_line(gitignore, ".project-memory/")
    gitignore_changed = any((
        ensure_line(gitignore, "graphify-out/runtime/"),
        ensure_line(gitignore, "graphify-out/cache/"),
        ensure_line(gitignore, "graphify-out/memory/"),
        ensure_line(gitignore, "graphify-out/reflections/"),
        ensure_line(gitignore, "graphify-out/cost.json"),
        ensure_line(gitignore, "graphify-out/.graphify_*"),
        ensure_line(gitignore, "graphify-out/.vocab.txt"),
        ensure_line(gitignore, "graphify-out/before-*.json"),
        ensure_line(gitignore, "graphify-out/pre-graphify-*/"),
        ensure_line(gitignore, "graphify-out/graph.html"),
        ensure_line(gitignore, "graphify-out/????-??-??/"),
        ensure_line(gitignore, ".project-memory/metrics.jsonl"),
        ensure_line(gitignore, ".project-memory/source-reads.jsonl"),
        removed_blanket_graph, removed_blanket_memory,
    ))
    graphifyignore = args.project / ".graphifyignore"
    graphifyignore_changed = any((
        ensure_line(graphifyignore, ".project-memory/"),
        ensure_line(graphifyignore, "graphify-out/"),
        ensure_line(graphifyignore, ".git/"),
        ensure_line(graphifyignore, "__pycache__/"),
        ensure_line(graphifyignore, "*.egg-info/"),
        ensure_line(graphifyignore, ".pytest_cache/"),
    ))
    graph = args.project / "graphify-out" / "graph.json"
    graph_action = "existing" if graph.exists() else "not_requested"
    if args.with_graphify and not graph.exists():
        graphify_bridge.build(args.project)
        graph_action = "created"
    fingerprint_migration = upgrade_graph_state_fingerprint(args.project, memory)
    print_json({
        "project": str(args.project),
        "memory_root": str(memory),
        "memory_created": created,
        "agents_file": str(target),
        "agents_changed": changed,
        "evolution_file": str(evolution),
        "evolution_created": evolution_created,
        "gitignore_changed": gitignore_changed,
        "graphifyignore_changed": graphifyignore_changed,
        "graphify": graph_action,
        "fingerprint_migration": fingerprint_migration,
        "next": f'gpm doctor --project "{args.project}"',
    })


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gpm", description="Structured project memory companion for Graphify")
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    def project_command(name: str, handler: Any) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.add_argument("--project", type=project_path, default=Path.cwd())
        command.set_defaults(handler=handler)
        return command
    init = project_command("init", command_init); init.add_argument("--name")
    project_command("status", command_status)
    state = project_command("state", command_state); state.add_argument("--objective"); state.add_argument("--phase"); state.add_argument("--current-task"); state.add_argument("--next-action"); state.add_argument("--task-id")
    work_add = project_command("work-add", command_work_add); work_add.add_argument("title"); work_add.add_argument("--status", choices=["pending", "in_progress", "completed"], default="pending"); work_add.add_argument("--kind", default="task"); work_add.add_argument("--source", default="")
    work_update = project_command("work-update", command_work_update); work_update.add_argument("id"); work_update.add_argument("--status", choices=["pending", "in_progress", "completed"], required=True)
    query = project_command("query", command_query); query.add_argument("question"); query.add_argument("--budget", type=int); query.add_argument("--limit", type=int, default=8); query.add_argument("--quality", choices=["unrated", "correct", "partial", "incorrect"], default="unrated"); query.add_argument("--adaptive", action="store_true"); query.add_argument("--initial-budget", type=int, default=400); query.add_argument("--max-budget", type=int, default=2400); query.add_argument("--coverage-threshold", type=float, default=0.5); query.add_argument("--task"); query.add_argument("--hydrate", action=argparse.BooleanOptionalAction, default=True); query.add_argument("--hydrate-files", type=int, default=3); query.add_argument("--hydrate-radius", type=int, default=10); query.add_argument("--hydrate-max-tokens", type=int, default=900)
    decision = project_command("decision", command_decision); decision.add_argument("text"); decision.add_argument("--reason", default=""); decision.add_argument("--source", default=""); decision.add_argument("--start-line", type=int); decision.add_argument("--end-line", type=int); decision.add_argument("--task")
    issue = project_command("issue", command_issue); issue.add_argument("title"); issue.add_argument("--details", default=""); issue.add_argument("--status", choices=["open", "resolved"], default="open"); issue.add_argument("--source", default=""); issue.add_argument("--start-line", type=int); issue.add_argument("--end-line", type=int); issue.add_argument("--task")
    checkpoint = project_command("checkpoint", command_checkpoint); checkpoint.add_argument("summary"); checkpoint.add_argument("--no-graphify", action="store_true")
    project_command("metrics", command_metrics)
    source = project_command("source-add", command_source_add); source.add_argument("paths", nargs="+"); source.add_argument("--task"); source.add_argument("--start-line", type=int); source.add_argument("--end-line", type=int); source.add_argument("--allow-sensitive", action="store_true")
    fact_add = project_command("fact-add", command_fact_add); fact_add.add_argument("subject"); fact_add.add_argument("predicate"); fact_add.add_argument("value"); fact_add.add_argument("--source", default=""); fact_add.add_argument("--start-line", type=int); fact_add.add_argument("--end-line", type=int); fact_add.add_argument("--confidence", type=float)
    fact_status = project_command("fact-status", command_fact_status); fact_status.add_argument("id"); fact_status.add_argument("status", choices=["active", "superseded", "revoked", "stale", "needs_validation"]); fact_status.add_argument("--reason", default="")
    facts = project_command("facts", command_facts); facts.add_argument("--status", choices=["active", "superseded", "revoked", "stale", "needs_validation"])
    project_command("validate-facts", command_validate_facts)
    project_command("consolidate", command_consolidate)
    report = project_command("report", command_report); report.add_argument("--task"); report.add_argument("--all", action="store_true")
    project_command("benchmark", command_benchmark)
    project_command("freshness", command_freshness)
    project_command("doctor", command_doctor)
    install = project_command("install", command_install)
    install.add_argument("--name")
    install.add_argument("--with-graphify", action="store_true")
    return root


def main() -> None:
    args = parser().parse_args()
    try:
        args.handler(args)
    except (RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
