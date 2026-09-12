from __future__ import annotations

import re
from pathlib import Path

AGENTS_START = "<!-- project-memory:start -->"
AGENTS_END = "<!-- project-memory:end -->"
_MANAGED_SENTINEL = "<!-- project-memory:managed -->"
_MANAGED_RE = re.compile(
    re.escape(AGENTS_START) + r".*?" + re.escape(AGENTS_END),
    re.DOTALL,
)


def normalize_managed_source(rel_path: str, data: bytes) -> bytes:
    """Return source-significant bytes for a project file.

    Only the GPM-owned block in root AGENTS.md is normalized away. Human-authored
    content before/after the block remains byte-significant.
    """
    normalized = rel_path.replace("\\", "/")
    if normalized != "AGENTS.md":
        return data
    text = data.decode("utf-8", errors="replace")
    # Git blobs are stored with LF while Windows working trees commonly use CRLF.
    # Line-ending translation alone is not a source-significant change in AGENTS.md.
    # Normalize EOLs before removing the GPM-owned block so managed-only edits compare
    # equal across Git and the Windows working tree, while human text remains significant.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MANAGED_RE.sub(_MANAGED_SENTINEL, text)
    return text.encode("utf-8")


def managed_source_equal(rel_path: str, left: bytes, right: bytes) -> bool:
    return normalize_managed_source(rel_path, left) == normalize_managed_source(rel_path, right)


def is_agents_managed_only_change(rel_path: str, current: bytes, baseline: bytes) -> bool:
    normalized = rel_path.replace("\\", "/")
    return normalized == "AGENTS.md" and managed_source_equal(normalized, current, baseline)


def read_path_bytes(project: Path, rel_path: str) -> bytes:
    path = project / Path(rel_path)
    return path.read_bytes() if path.is_file() else b""
