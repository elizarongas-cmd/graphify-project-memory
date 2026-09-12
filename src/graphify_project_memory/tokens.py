from __future__ import annotations

import math


def estimate_tokens(text: str) -> int:
    """Conservative local estimate suitable for comparisons without API calls."""
    return 0 if not text else math.ceil(len(text) / 4)


def context_reduction(baseline: int, actual: int) -> tuple[int, float]:
    """Return estimated context avoided, not provider-billed token savings."""
    avoided = max(0, baseline - actual)
    percent = round((avoided / baseline * 100), 2) if baseline else 0.0
    return avoided, percent


def savings(baseline: int, actual: int) -> tuple[int, float]:
    """Backward-compatible alias for pre-0.3.1 callers."""
    return context_reduction(baseline, actual)
