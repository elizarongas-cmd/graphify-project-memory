from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .storage import append_jsonl, read_jsonl, utc_now

FACTS_FILE = "facts.jsonl"
FACT_STATUSES = {"active", "superseded", "revoked", "stale", "needs_validation"}


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value.strip().lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", value)


def canonical_key(subject: str, predicate: str) -> str:
    raw = f"{_norm(subject)}\0{_norm(predicate)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def fact_id(subject: str, predicate: str, value: str) -> str:
    raw = f"{canonical_key(subject, predicate)}\0{_norm(value)}"
    return "FACT-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def current_facts(root: Path) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in read_jsonl(root / FACTS_FILE):
        identifier = str(event.get("fact_id", ""))
        if identifier:
            latest[identifier] = event
    return sorted(latest.values(), key=lambda item: (str(item.get("canonical_key", "")), str(item.get("fact_id", ""))))


def active_facts(root: Path) -> list[dict[str, Any]]:
    return [item for item in current_facts(root) if item.get("status") in {"active", "needs_validation"}]


def add_fact(
    root: Path,
    subject: str,
    predicate: str,
    value: str,
    provenance: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> dict[str, Any]:
    key = canonical_key(subject, predicate)
    identifier = fact_id(subject, predicate, value)
    existing = current_facts(root)
    same = next((item for item in existing if item.get("fact_id") == identifier and item.get("status") == "active"), None)
    if same:
        supplied_provenance = provenance or {}
        if supplied_provenance and supplied_provenance != (same.get("provenance") or {}):
            now = utc_now()
            refreshed = dict(same)
            refreshed.update({
                "updated_at": now,
                "event": "reassert",
                "provenance": supplied_provenance,
            })
            if confidence is not None:
                refreshed["confidence"] = max(0.0, min(1.0, float(confidence)))
            append_jsonl(root / FACTS_FILE, refreshed)
            return refreshed
        result = dict(same)
        result["duplicate"] = True
        return result

    now = utc_now()
    superseded: list[str] = []
    for item in existing:
        if item.get("canonical_key") == key and item.get("status") == "active" and item.get("fact_id") != identifier:
            event = dict(item)
            event.update({
                "status": "superseded",
                "superseded_by": identifier,
                "updated_at": now,
                "event": "supersede",
            })
            append_jsonl(root / FACTS_FILE, event)
            superseded.append(str(item.get("fact_id")))

    record: dict[str, Any] = {
        "fact_id": identifier,
        "canonical_key": key,
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "event": "assert",
        "provenance": provenance or {},
    }
    if confidence is not None:
        record["confidence"] = max(0.0, min(1.0, float(confidence)))
    if superseded:
        record["supersedes"] = superseded
    append_jsonl(root / FACTS_FILE, record)
    return record


def set_fact_status(root: Path, identifier: str, status: str, reason: str = "") -> dict[str, Any]:
    if status not in FACT_STATUSES:
        raise ValueError(f"Unsupported fact status: {status}")
    item = next((value for value in current_facts(root) if value.get("fact_id") == identifier), None)
    if not item:
        raise RuntimeError(f"Fact not found: {identifier}")
    event = dict(item)
    event.update({"status": status, "updated_at": utc_now(), "event": "status_change"})
    if reason:
        event["status_reason"] = reason
    append_jsonl(root / FACTS_FILE, event)
    return event


def validate_facts(root: Path, project: Path, source_revision: str | None) -> dict[str, Any]:
    changed: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for item in current_facts(root):
        if item.get("status") not in {"active", "needs_validation"}:
            continue
        provenance = item.get("provenance") or {}
        rel = provenance.get("path")
        reason = None
        conflict_type = None
        if rel:
            path = project / str(rel)
            if not path.is_file():
                reason = "provenance_source_missing"
                conflict_type = "memory_vs_source"
        observed_revision = provenance.get("source_revision")
        if reason is None and rel and observed_revision and source_revision and observed_revision != source_revision:
            reason = "source_revision_advanced"
            conflict_type = "memory_vs_source_revision"
        if reason and item.get("status") != "needs_validation":
            updated = set_fact_status(root, str(item["fact_id"]), "needs_validation", reason)
            changed.append(updated)
        if reason:
            conflicts.append({"fact_id": item.get("fact_id"), "type": conflict_type, "reason": reason, "path": rel})
    return {"checked": len(current_facts(root)), "changed": changed, "conflicts": conflicts}


def consolidate(root: Path) -> dict[str, Any]:
    facts = current_facts(root)
    active = [item for item in facts if item.get("status") == "active"]
    review = [item for item in facts if item.get("status") == "needs_validation"]
    lines = ["# Consolidated Project Memory", "", f"Generated: {utc_now()}", ""]
    if active:
        lines += ["## Active facts", ""]
        for item in active:
            lines.append(f"- `{item['fact_id']}` **{item['subject']} / {item['predicate']}**: {item['value']}")
        lines.append("")
    if review:
        lines += ["## Needs validation", ""]
        for item in review:
            lines.append(f"- `{item['fact_id']}` {item['subject']} / {item['predicate']}: {item['value']}")
        lines.append("")
    decisions = read_jsonl(root / "decisions.jsonl")
    if decisions:
        lines += ["## Recent active decisions", ""]
        for item in [d for d in decisions if d.get("status", "active") == "active"][-12:]:
            lines.append(f"- `{item.get('id','')}` {item.get('decision','')}")
        lines.append("")
    checkpoints = read_jsonl(root / "checkpoints.jsonl")
    if checkpoints:
        lines += ["## Recent checkpoints", ""]
        for item in checkpoints[-8:]:
            lines.append(f"- {item.get('timestamp','')}: {item.get('summary','')}")
        lines.append("")
    target = root / "summaries" / "consolidated.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "target": str(target),
        "facts_total": len(facts),
        "facts_active": len(active),
        "facts_needs_validation": len(review),
        "decisions_considered": len(decisions),
        "checkpoints_considered": len(checkpoints),
    }
