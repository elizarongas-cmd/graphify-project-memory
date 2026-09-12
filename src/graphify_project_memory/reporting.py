from __future__ import annotations

from collections import Counter
from typing import Any

from .tokens import context_reduction


def summarize(metrics: list[dict[str, Any]], source_reads: list[dict[str, Any]], task_id: str | None = None) -> dict[str, Any]:
    if task_id:
        metrics = [item for item in metrics if item.get("task_id", "unassigned") == task_id]
        source_reads = [item for item in source_reads if item.get("task_id", "unassigned") == task_id]
    baseline = sum(int(item.get("baseline_tokens", 0)) for item in metrics)
    retrieval = sum(int(item.get("total_retrieval_tokens", 0)) for item in metrics)
    unique_sources: dict[tuple[str, str, int | None, int | None], dict[str, Any]] = {}
    for item in source_reads:
        key = (
            str(item.get("task_id", "unassigned")),
            str(item.get("path", "")),
            item.get("start_line"),
            item.get("end_line"),
        )
        unique_sources[key] = item
    source_reads = list(unique_sources.values())
    source_tokens = sum(int(item.get("tokens", 0)) for item in source_reads)
    actual = retrieval + source_tokens
    avoided, percent = context_reduction(baseline, actual)
    quality = Counter(item.get("quality", "unrated") for item in metrics)
    tiers = Counter(item.get("context_tier", "legacy") for item in metrics)
    reasons = Counter(item.get("escalation_reason", "") for item in metrics if item.get("escalation_reason"))
    coverages = [float(item.get("memory_coverage", 0.0)) for item in metrics if item.get("memory_coverage") is not None]
    return {
        "scope": task_id or "all",
        "queries": len(metrics),
        "baseline_tokens": baseline,
        "memory_tokens": sum(int(item.get("memory_tokens", 0)) for item in metrics),
        "graph_tokens": sum(int(item.get("graph_tokens", 0)) for item in metrics),
        "source_tokens": source_tokens,
        "retrieval_tokens": actual,
        "context_avoided_estimate": avoided,
        "context_reduction_percent": percent,
        # Kept for consumers of 0.3.0; semantics are now documented as estimates.
        "saved_tokens": avoided,
        "saving_percent": percent,
        "adaptive_expansions": sum(bool(item.get("expanded")) for item in metrics),
        "quality": {name: quality.get(name, 0) for name in ("correct", "partial", "incorrect", "unrated")},
        "context_tiers": dict(tiers),
        "escalation_reasons": dict(reasons),
        "average_memory_coverage": round(sum(coverages) / len(coverages), 3) if coverages else None,
        "source_files": len({item.get("path") for item in source_reads if item.get("path")}),
        "memory_candidates": sum(int(item.get("memory_candidates", 0)) for item in metrics),
        "memory_selected": sum(int(item.get("memory_selected", 0)) for item in metrics),
        "hydrated_files": sum(int(item.get("hydrated_files", 0)) for item in metrics),
        "hydrated_ranges": sum(int(item.get("hydrated_ranges", 0)) for item in metrics),
        "queries_with_memory_needs_validation": sum(bool(item.get("memory_needs_validation")) for item in metrics),
    }
