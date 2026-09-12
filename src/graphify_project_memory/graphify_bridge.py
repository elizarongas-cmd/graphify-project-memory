from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def executable(project: Path) -> str | None:
    """Resolve Graphify globally or from a project's isolated runtime."""
    candidates = (
        project / "graphify-out" / "runtime" / "Scripts" / "graphify.exe",
        project / "graphify-out" / "runtime" / "bin" / "graphify",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return shutil.which("graphify")


def available(project: Path) -> bool:
    return executable(project) is not None


def _completed(project: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    command = executable(project)
    if command is None:
        raise RuntimeError(
            "Graphify CLI is unavailable. Install Graphify globally or provide "
            "graphify-out/runtime inside the project."
        )
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    return subprocess.run(
        [command, *arguments], cwd=project, text=True, capture_output=True,
        encoding="utf-8", errors="replace", check=False, env=environment,
    )


def run(project: Path, arguments: list[str], check: bool = True) -> str:
    completed = _completed(project, arguments)
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if check and completed.returncode:
        raise RuntimeError(output or f"Graphify exited with code {completed.returncode}")
    return output


def version(project: Path) -> str | None:
    if not available(project):
        return None
    output = run(project, ["--version"], check=False)
    match = re.search(r"(?:graphify\s*)?v?(\d+\.\d+\.\d+)", output, re.IGNORECASE)
    return match.group(1) if match else (output.strip() or None)


def capabilities(project: Path) -> dict[str, Any]:
    """Probe the installed CLI instead of assuming features from a version string."""
    if not available(project):
        return {"available": False, "version": None}
    root_help = run(project, ["--help"], check=False).lower()
    has_query = bool(re.search(r"\bquery\b", root_help))
    save_help = run(project, ["save-result", "--help"], check=False).lower() if "save-result" in root_help else ""

    # Graphify 0.9.57 treats `graphify query --help` as a literal query instead
    # of subcommand help. Probe argument acceptance directly with a sentinel
    # question. Parser errors prove lack of support; graph/data errors still mean
    # the CLI accepted --budget.
    query_budget = False
    if has_query:
        probe = _completed(project, ["query", "__gpm_capability_probe__", "--budget", "1"])
        probe_text = "\n".join(part.strip() for part in (probe.stdout, probe.stderr) if part.strip()).lower()
        parser_rejection = any(marker in probe_text for marker in (
            "unrecognized arguments", "unknown option", "no such option",
            "unexpected argument", "invalid option",
        ))
        query_budget = not parser_rejection

    return {
        "available": True,
        "version": version(project),
        "query": has_query,
        "query_budget": query_budget,
        "work_memory": "save-result" in root_help and "--outcome" in save_help,
        "reflection": bool(re.search(r"\breflect\b", root_help)),
        "diagnose": bool(re.search(r"\bdiagnose\b", root_help)),
    }


def query(project: Path, question: str, budget: int) -> str:
    return run(project, ["query", question, "--budget", str(budget)])


def benchmark(project: Path, graph_path: Path) -> str:
    return run(project, ["benchmark", str(graph_path)])


def checkpoint(project: Path, summary: str) -> dict[str, str]:
    outputs = {
        "update": run(project, ["update", "."]),
        "diagnose": run(project, ["diagnose", "multigraph"]),
    }
    caps = capabilities(project)
    if caps.get("work_memory"):
        run(project, [
            "save-result", "--question", "Project checkpoint", "--answer", summary,
            "--type", "query", "--outcome", "useful",
        ])
    if caps.get("reflection"):
        outputs["reflect"] = run(project, ["reflect"])
    return outputs


def build(project: Path) -> str:
    try:
        return run(project, [str(project), "--no-viz"])
    except RuntimeError as error:
        if "no LLM API key found" not in str(error).lower():
            raise
        return run(project, [str(project), "--code-only", "--no-viz"])
