from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .tokens import estimate_tokens

NODE_SOURCE = re.compile(r"NODE .*?\[src=(?P<src>[^\]]*?)\s+loc=L?(?P<line>\d+|None)")
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def graph_source_locations(graph_text: str, limit: int = 4) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for match in NODE_SOURCE.finditer(graph_text):
        src = match.group("src").strip()
        line_raw = match.group("line")
        if not src or line_raw == "None":
            continue
        line = int(line_raw)
        key = (src, line)
        if key in seen:
            continue
        seen.add(key)
        found.append({"path": src.replace("\\", "/"), "line": line})
        if len(found) >= limit:
            break
    return found


def hydrate_sources(project: Path, graph_text: str, limit: int = 4, radius: int = 12, max_tokens: int = 1200) -> dict[str, Any]:
    ranges: list[dict[str, Any]] = []
    chunks: list[str] = []
    total_tokens = 0
    for location in graph_source_locations(graph_text, limit=limit):
        rel = str(location["path"])
        path = (project / rel).resolve()
        try:
            path.relative_to(project.resolve())
        except ValueError:
            continue
        if path.name.lower() in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_SUFFIXES or not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        center = int(location["line"])
        start = max(1, center - radius)
        end = min(len(lines), center + radius)
        text = "\n".join(f"{idx}: {lines[idx-1]}" for idx in range(start, end + 1))
        tokens = estimate_tokens(text)
        if total_tokens + tokens > max_tokens:
            remaining = max_tokens - total_tokens
            if remaining <= 0:
                break
            # Simple character cap consistent with estimate_tokens (~4 chars/token).
            text = text[: remaining * 4]
            tokens = estimate_tokens(text)
        ranges.append({"path": rel, "start_line": start, "end_line": end, "tokens": tokens})
        chunks.append(f"SOURCE {rel}:L{start}-L{end}\n{text}")
        total_tokens += tokens
        if total_tokens >= max_tokens:
            break
    return {"text": "\n\n".join(chunks), "ranges": ranges, "tokens": total_tokens}
