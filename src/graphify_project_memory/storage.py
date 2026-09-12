from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 4
MEMORY_DIR = ".project-memory"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def memory_root(project: Path) -> Path:
    return project.resolve() / MEMORY_DIR


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    values: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values.append(json.loads(line))
    return values


def migrate_memory(root: Path) -> list[str]:
    config_path = root / "config.json"
    if not config_path.exists():
        return []
    config = load_json(config_path, {})
    previous = int(config.get("schema_version", 1))
    migrated: list[str] = []
    if previous < SCHEMA_VERSION:
        config["schema_version"] = SCHEMA_VERSION
        config.setdefault("migration_history", []).append({
            "from": previous, "to": SCHEMA_VERSION, "migrated_at": utc_now()
        })
        atomic_json(config_path, config)
        migrated.append(f"migration:{previous}->{SCHEMA_VERSION}")
        for filename in ("state.json", "work-items.json", "issues.json", "baseline.json", "graph-state.json"):
            path = root / filename
            default = {"captured_at": None} if filename == "graph-state.json" else {}
            value = load_json(path, default) or default
            value["schema_version"] = SCHEMA_VERSION
            if filename == "graph-state.json":
                value.setdefault("captured_at", None)
                git = value.get("git") or {}
                if "head" in git and "observed_head" not in git:
                    old_head = git.get("head")
                    git["source_revision"] = old_head
                    git["observed_head"] = old_head
                    git.pop("head", None)
                if "content_sha256" in git and "source_content_sha256" not in git:
                    git["source_content_sha256"] = git.pop("content_sha256")
                if "content_file_count" in git and "source_file_count" not in git:
                    git["source_file_count"] = git.pop("content_file_count")
                value["git"] = git
            atomic_json(path, value)
    source_reads = root / "source-reads.jsonl"
    if not source_reads.exists():
        source_reads.write_text("", encoding="utf-8")
        migrated.append("source-reads.jsonl")
    facts = root / "facts.jsonl"
    if not facts.exists():
        facts.write_text("", encoding="utf-8")
        migrated.append("facts.jsonl")
    graph_state = root / "graph-state.json"
    if not graph_state.exists():
        atomic_json(graph_state, {"schema_version": SCHEMA_VERSION, "captured_at": None})
        migrated.append("graph-state.json")
    return migrated


def initialize(project: Path, name: str | None = None) -> tuple[Path, list[str]]:
    root = memory_root(project)
    root.mkdir(parents=True, exist_ok=True)
    (root / "summaries").mkdir(exist_ok=True)
    created: list[str] = []
    defaults: dict[str, Any] = {
        "config.json": {
            "schema_version": SCHEMA_VERSION,
            "project_name": name or project.resolve().name,
            "graph_dir": "graphify-out",
            "query_budget": 600,
            "shared_memory": True,
            "created_at": utc_now(),
        },
        "state.json": {
            "schema_version": SCHEMA_VERSION,
            "objective": "",
            "phase": "initialized",
            "current_task": "",
            "next_action": "",
            "updated_at": utc_now(),
        },
        "work-items.json": {"schema_version": SCHEMA_VERSION, "items": []},
        "issues.json": {"schema_version": SCHEMA_VERSION, "items": []},
        "baseline.json": {"schema_version": SCHEMA_VERSION, "captured": False},
        "graph-state.json": {"schema_version": SCHEMA_VERSION, "captured_at": None, "git": {}},
    }
    for filename, value in defaults.items():
        target = root / filename
        if not target.exists():
            atomic_json(target, value)
            created.append(filename)
    for filename in ("decisions.jsonl", "checkpoints.jsonl", "metrics.jsonl", "source-reads.jsonl", "facts.jsonl"):
        target = root / filename
        if not target.exists():
            target.write_text("", encoding="utf-8")
            created.append(filename)
    summary = root / "summaries" / "project.md"
    if not summary.exists():
        summary.write_text(f"# {name or project.resolve().name}\n\nCompact project summary.\n", encoding="utf-8")
        created.append("summaries/project.md")
    created.extend(migrate_memory(root))
    return root, created


def require_memory(project: Path) -> Path:
    root = memory_root(project)
    if not (root / "config.json").exists():
        raise RuntimeError(f"Project Memory is not initialized at {project.resolve()}")
    migrate_memory(root)
    return root


STOP_TERMS = {
    "que", "qué", "como", "cómo", "cual", "cuál", "para", "por", "con", "del", "las", "los", "una", "uno",
    "what", "which", "where", "when", "why", "how", "the", "and", "for", "with", "from", "this", "that",
    "should", "would", "could", "work", "hacer", "ahora", "actual", "actualmente",
}


def normalized_terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFD", value.lower())
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    terms = {term for term in re.findall(r"[a-z0-9_]{3,}", normalized)}
    terms.update(part for term in list(terms) for part in term.split("_") if len(part) >= 3)
    terms.update(term[:-1] for term in list(terms) if len(term) > 4 and term.endswith("s"))
    aliases = {
        "next": {"sigue", "siguiente", "proxima", "proximo", "pending", "pendiente"},
        "done": {"terminamos", "terminada", "terminado", "completada", "completado", "completed", "complete"},
        "decision": {"decidimos", "decision", "decisiones", "acordamos"},
        "issue": {"issue", "issues", "problema", "problemas", "error", "errores"},
    }
    for canonical, variants in aliases.items():
        if terms & variants:
            terms.add(canonical)
    return terms


def meaningful_terms(value: str) -> set[str]:
    return {term for term in normalized_terms(value) if term not in STOP_TERMS}


def _string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


def query_memory_records(project: Path, question: str, limit: int = 8) -> list[dict[str, Any]]:
    root = require_memory(project)
    terms = meaningful_terms(question)
    candidates: list[dict[str, Any]] = []

    def add_candidate(source: str, value: Any) -> None:
        text = value if isinstance(value, str) else " | ".join(_string_values(value))
        record_terms = normalized_terms(text)
        matched = sorted(terms & record_terms)
        if matched:
            candidate = {
                "score": len(matched),
                "source": source,
                "text": text[:700],
                "matched_terms": matched,
            }
            if isinstance(value, dict) and value.get("status"):
                candidate["status"] = value.get("status")
            candidates.append(candidate)

    for filename in ("state.json", "baseline.json"):
        add_candidate(filename, load_json(root / filename, {}))
    for filename in ("work-items.json", "issues.json"):
        for index, value in enumerate(load_json(root / filename, {"items": []}).get("items", []), start=1):
            add_candidate(f"{filename}:{index:04d}", value)
    for filename in ("decisions.jsonl", "checkpoints.jsonl"):
        for index, value in enumerate(read_jsonl(root / filename), start=1):
            add_candidate(f"{filename}:{index:04d}", value)
    latest_facts: dict[str, dict[str, Any]] = {}
    for value in read_jsonl(root / "facts.jsonl"):
        identifier = str(value.get("fact_id", ""))
        if identifier:
            latest_facts[identifier] = value
    for identifier, value in latest_facts.items():
        if value.get("status") in {"active", "needs_validation"}:
            add_candidate(f"facts.jsonl:{identifier}", value)
    for summary in (root / "summaries").glob("*.md"):
        add_candidate(f"summaries/{summary.name}", summary.read_text(encoding="utf-8"))
    candidates.sort(key=lambda item: (-int(item["score"]), str(item["source"])))
    return candidates[:limit]


def memory_coverage(question: str, records: list[dict[str, Any]]) -> float:
    terms = meaningful_terms(question)
    if not terms:
        return 1.0 if records else 0.0
    matched: set[str] = set()
    for record in records:
        matched.update(str(term) for term in record.get("matched_terms", []))
    return round(len(matched & terms) / len(terms), 3)


def query_memory(project: Path, question: str, limit: int = 8) -> str:
    records = query_memory_records(project, question, limit)
    return "\n".join(f"[{record['source']}] {record['text']}" for record in records)
