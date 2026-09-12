from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .storage import SCHEMA_VERSION, atomic_json, load_json, utc_now
from .managed import normalize_managed_source, is_agents_managed_only_change, read_path_bytes

GRAPH_STATE_FILE = "graph-state.json"
SOURCE_FINGERPRINT_VERSION = 2
_EXCLUDED_PREFIXES = (".project-memory/", "graphify-out/")


def _run_git(project: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args], cwd=project, text=True, capture_output=True, check=False,
        encoding="utf-8", errors="replace",
    )
    return completed.returncode, completed.stdout.rstrip()


def _relevant_git_paths(project: Path) -> list[str]:
    code, output = _run_git(project, ["ls-files", "-co", "--exclude-standard"])
    if code != 0:
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for raw in output.splitlines():
        rel = raw.strip().replace("\\", "/")
        if not rel or rel in seen or rel.startswith(_EXCLUDED_PREFIXES):
            continue
        path = project / Path(rel)
        if not path.is_file():
            continue
        seen.add(rel)
        paths.append(rel)
    return sorted(paths)


def _fallback_project_paths(project: Path) -> list[str]:
    excluded_dirs = {
        ".git", ".project-memory", "graphify-out", "__pycache__", ".pytest_cache",
        ".venv", "venv", "node_modules", "build", "dist",
    }
    paths: list[str] = []
    for path in project.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(project)
        if any(part in excluded_dirs or part.endswith(".egg-info") for part in rel_path.parts[:-1]):
            continue
        paths.append(rel_path.as_posix())
    return sorted(set(paths))


def relevant_project_paths(project: Path) -> list[str]:
    paths = _relevant_git_paths(project)
    return paths if paths else _fallback_project_paths(project)


def working_tree_fingerprint(project: Path) -> dict[str, Any]:
    paths = relevant_project_paths(project)
    if not paths:
        return {"content_sha256": None, "file_count": 0, "fingerprint_version": SOURCE_FINGERPRINT_VERSION}
    digest = hashlib.sha256()
    count = 0
    for rel in paths:
        path = project / Path(rel)
        data = normalize_managed_source(rel, path.read_bytes())
        digest.update(rel.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
        count += 1
    return {"content_sha256": digest.hexdigest(), "file_count": count, "fingerprint_version": SOURCE_FINGERPRINT_VERSION}


def working_tree_sha256(project: Path) -> str | None:
    return working_tree_fingerprint(project)["content_sha256"]


def _git_head_file_bytes(project: Path, rel_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"], cwd=project, capture_output=True, check=False
    )
    return completed.stdout if completed.returncode == 0 else b""


def _status_line_is_managed_only(project: Path, line: str) -> bool:
    if len(line) < 4:
        return False
    raw_path = line[3:].strip().strip('"').replace("\\", "/")
    if raw_path != "AGENTS.md":
        return False
    current = read_path_bytes(project, raw_path)
    baseline = _git_head_file_bytes(project, raw_path)
    return is_agents_managed_only_change(raw_path, current, baseline)


def git_snapshot(project: Path) -> dict[str, Any]:
    head_code, head = _run_git(project, ["rev-parse", "HEAD"])
    status_code, status = _run_git(project, ["status", "--porcelain=v1", "--untracked-files=all"])
    if status_code == 0:
        relevant_lines = []
        for line in status.splitlines():
            path = line[3:].strip().strip('"') if len(line) >= 4 else ""
            normalized = path.replace("\\", "/")
            if normalized.startswith(_EXCLUDED_PREFIXES):
                continue
            if _status_line_is_managed_only(project, line):
                continue
            relevant_lines.append(line)
        status_text = "\n".join(relevant_lines)
    else:
        status_text = ""
    fingerprint = working_tree_fingerprint(project)
    observed_head = head if head_code == 0 else None
    return {
        "observed_head": observed_head,
        "dirty": bool(status_text),
        "status_hash": hashlib.sha256(status_text.encode("utf-8")).hexdigest() if status_text else None,
        "source_content_sha256": fingerprint["content_sha256"],
        "source_file_count": fingerprint["file_count"],
        "source_fingerprint_version": fingerprint["fingerprint_version"],
        # 0.3.x compatibility aliases. New code should prefer source_* names.
        "head": observed_head,
        "content_sha256": fingerprint["content_sha256"],
        "content_file_count": fingerprint["file_count"],
        "fingerprint_version": fingerprint["fingerprint_version"],
    }


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _saved_git_compat(saved: dict[str, Any]) -> dict[str, Any]:
    git = dict(saved.get("git") or {})
    if "source_revision" not in git and "head" in git:
        git["source_revision"] = git.get("head")
    if "observed_head" not in git:
        git["observed_head"] = git.get("head") or git.get("source_revision")
    if "source_content_sha256" not in git and "content_sha256" in git:
        git["source_content_sha256"] = git.get("content_sha256")
    if "source_file_count" not in git and "content_file_count" in git:
        git["source_file_count"] = git.get("content_file_count")
    git.setdefault("source_fingerprint_version", 1)
    return git



def _git_blob_at(project: Path, revision: str, rel_path: str) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{rel_path}"], cwd=project, capture_output=True, check=False
    )
    return completed.stdout if completed.returncode == 0 else b""


def committed_source_changed(project: Path, source_revision: str, observed_head: str) -> bool:
    if not source_revision or not observed_head or source_revision == observed_head:
        return False
    code, output = _run_git(project, ["diff", "--name-only", source_revision, observed_head])
    if code != 0:
        return True
    for raw in output.splitlines():
        rel = raw.strip().replace("\\", "/")
        if not rel or rel.startswith(_EXCLUDED_PREFIXES):
            continue
        if rel == "AGENTS.md":
            before = _git_blob_at(project, source_revision, rel)
            after = _git_blob_at(project, observed_head, rel)
            if is_agents_managed_only_change(rel, after, before):
                continue
        return True
    return False


def upgrade_graph_state_fingerprint(project: Path, memory_root: Path) -> dict[str, Any]:
    """Upgrade a captured v1 source fingerprint to v2 only when source equivalence is provable.

    This is intentionally conservative: metadata-only commits plus GPM's managed AGENTS.md
    block may be rebased without a checkpoint, but any source-significant dirty file or commit
    prevents automatic migration.
    """
    path = memory_root / GRAPH_STATE_FILE
    saved = load_json(path, {}) or {}
    if not saved.get("captured_at"):
        return {"changed": False, "reason": "no_baseline"}
    saved_git = _saved_git_compat(saved)
    if int(saved_git.get("source_fingerprint_version") or 1) >= SOURCE_FINGERPRINT_VERSION:
        return {"changed": False, "reason": "already_current"}
    source_revision = saved_git.get("source_revision")
    current = git_snapshot(project)
    observed_head = current.get("observed_head")
    if not source_revision or not observed_head:
        return {"changed": False, "reason": "revision_unavailable"}
    if current.get("dirty"):
        return {"changed": False, "reason": "source_dirty"}
    if committed_source_changed(project, source_revision, observed_head):
        return {"changed": False, "reason": "source_changed"}
    git_state = dict(saved.get("git") or {})
    git_state.pop("head", None)
    git_state.pop("content_sha256", None)
    git_state.pop("content_file_count", None)
    git_state.update({
        "source_revision": source_revision,
        "observed_head": observed_head,
        "dirty": current.get("dirty"),
        "status_hash": current.get("status_hash"),
        "source_content_sha256": current.get("source_content_sha256"),
        "source_file_count": current.get("source_file_count"),
        "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
    })
    saved["git"] = git_state
    saved["fingerprint_migrated_at"] = utc_now()
    atomic_json(path, saved)
    return {
        "changed": True,
        "reason": "metadata_only_legacy_fingerprint",
        "source_revision": source_revision,
        "observed_head": observed_head,
    }

def capture_graph_state(project: Path, memory_root: Path, graphify_version: str | None = None) -> dict[str, Any]:
    graph = project / "graphify-out" / "graph.json"
    manifest = project / "graphify-out" / "manifest.json"
    current = git_snapshot(project)
    previous = load_json(memory_root / GRAPH_STATE_FILE, {}) or {}
    previous_git = _saved_git_compat(previous)
    same_source = (
        previous_git.get("source_content_sha256") is not None
        and previous_git.get("source_content_sha256") == current.get("source_content_sha256")
    )
    source_revision = previous_git.get("source_revision") if same_source else current.get("observed_head")
    git_state = {
        "source_revision": source_revision,
        "observed_head": current.get("observed_head"),
        "dirty": current.get("dirty"),
        "status_hash": current.get("status_hash"),
        "source_content_sha256": current.get("source_content_sha256"),
        "source_file_count": current.get("source_file_count"),
        "source_fingerprint_version": SOURCE_FINGERPRINT_VERSION,
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "captured_at": utc_now(),
        "git": git_state,
        "graph_sha256": file_sha256(graph),
        "manifest_sha256": file_sha256(manifest),
        "graphify_version": graphify_version,
    }
    atomic_json(memory_root / GRAPH_STATE_FILE, snapshot)
    return snapshot


def evaluate_freshness(project: Path, memory_root: Path) -> dict[str, Any]:
    saved = load_json(memory_root / GRAPH_STATE_FILE, {}) or {}
    current_git = git_snapshot(project)
    current_graph = file_sha256(project / "graphify-out" / "graph.json")
    current_manifest = file_sha256(project / "graphify-out" / "manifest.json")
    reasons: list[str] = []
    warnings: list[str] = []

    if not saved or not saved.get("captured_at"):
        reasons.append("no_graph_state_baseline")
        effective_source_revision = current_git.get("observed_head")
    else:
        saved_git = _saved_git_compat(saved)
        saved_content = saved_git.get("source_content_sha256")
        current_content = current_git.get("source_content_sha256")
        source_changed = False
        if saved_content is None:
            reasons.append("working_tree_fingerprint_missing")
            source_changed = True
        elif saved_content != current_content:
            reasons.append("working_tree_changed")
            source_changed = True

        saved_head = saved_git.get("observed_head")
        current_head = current_git.get("observed_head")
        head_changed = saved_head != current_head
        if head_changed:
            if source_changed:
                reasons.append("git_head_changed_with_source_change")
            else:
                warnings.append("git_head_changed_without_source_change")

        effective_source_revision = (
            current_head if source_changed else saved_git.get("source_revision") or current_head
        )
        graph_changed = saved.get("graph_sha256") != current_graph
        manifest_changed = saved.get("manifest_sha256") != current_manifest
        if graph_changed:
            warnings.append("graph_changed_after_source_change" if source_changed else "graph_drift_without_source_change")
        if manifest_changed:
            warnings.append("manifest_changed_after_source_change" if source_changed else "manifest_drift_without_source_change")

    if current_graph is None:
        reasons.append("graph_missing")
    current_view = dict(current_git)
    current_view["effective_source_revision"] = effective_source_revision
    return {
        "fresh": not reasons,
        "reasons": reasons,
        "warnings": warnings,
        "baseline": saved or None,
        "current": {
            "git": current_view,
            "graph_sha256": current_graph,
            "manifest_sha256": current_manifest,
        },
    }
