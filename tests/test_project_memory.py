from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from graphify_project_memory.cli import (
    _graph_escalation_reason,
    _needs_graph,
    _provenance,
    command_install,
    command_source_add,
    parse_benchmark,
)
from graphify_project_memory import graphify_bridge
from graphify_project_memory.freshness import (
    capture_graph_state, evaluate_freshness, git_snapshot, working_tree_fingerprint,
    upgrade_graph_state_fingerprint,
)
from graphify_project_memory.storage import (
    SCHEMA_VERSION,
    append_jsonl,
    atomic_json,
    initialize,
    load_json,
    memory_coverage,
    query_memory,
    query_memory_records,
    read_jsonl,
    require_memory,
)
from graphify_project_memory.reporting import summarize
from graphify_project_memory.tokens import context_reduction, estimate_tokens, savings

from graphify_project_memory.facts import add_fact, current_facts, set_fact_status, validate_facts, consolidate
from graphify_project_memory.hydration import graph_source_locations, hydrate_sources


class ProjectMemoryTests(unittest.TestCase):
    def test_initialize_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, first = initialize(project, "Demo")
            _, second = initialize(project, "Demo")
            self.assertTrue(first)
            self.assertEqual(second, [])
            self.assertEqual(load_json(root / "config.json")["project_name"], "Demo")
            self.assertEqual(load_json(root / "config.json")["schema_version"], SCHEMA_VERSION)
            self.assertTrue((root / "graph-state.json").exists())

    def test_query_finds_decision_and_reports_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            append_jsonl(root / "decisions.jsonl", {"decision": "Use port 4320 for scripts studio"})
            records = query_memory_records(project, "scripts studio port")
            self.assertIn("4320", query_memory(project, "scripts studio port"))
            self.assertGreater(memory_coverage("scripts studio port", records), 0.5)

    def test_jsonl_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "values.jsonl"
            append_jsonl(target, {"value": "á"})
            self.assertEqual(read_jsonl(target), [{"value": "á"}])

    def test_token_math_and_semantics(self) -> None:
        self.assertEqual(estimate_tokens("12345678"), 2)
        self.assertEqual(context_reduction(100, 25), (75, 75.0))
        self.assertEqual(savings(100, 25), (75, 75.0))

    def test_parse_graphify_benchmark(self) -> None:
        parsed = parse_benchmark("Corpus: 29,800 words → ~39,733 tokens\nAvg query cost:  ~1,032 tokens\nReduction: 38.5x")
        self.assertEqual(parsed["corpus_tokens"], 39733)
        self.assertEqual(parsed["average_graph_query_tokens"], 1032)
        self.assertEqual(parsed["graph_reduction_x"], 38.5)


    def test_capabilities_detects_query_budget_when_subcommand_help_is_not_help(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            fake = subprocess.CompletedProcess(args=["graphify"], returncode=0, stdout="No matching nodes found.", stderr="")
            with patch("graphify_project_memory.graphify_bridge.available", return_value=True), \
                 patch("graphify_project_memory.graphify_bridge.run") as mocked_run, \
                 patch("graphify_project_memory.graphify_bridge._completed", return_value=fake):
                mocked_run.side_effect = lambda _project, args, check=False: (
                    "usage: graphify ... query ... save-result ... reflect ... diagnose ..."
                    if args == ["--help"] else
                    "usage: save-result --outcome {useful,dead_end,corrected}"
                    if args[:1] == ["save-result"] else
                    "graphify 0.9.57"
                )
                caps = graphify_bridge.capabilities(project)
            self.assertTrue(caps["query"])
            self.assertTrue(caps["query_budget"])
            self.assertTrue(caps["work_memory"])

    def test_resolves_isolated_windows_graphify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            executable = project / "graphify-out" / "runtime" / "Scripts" / "graphify.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            self.assertEqual(graphify_bridge.executable(project), str(executable))

    def test_install_is_idempotent_and_keeps_shareable_state_trackable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / ".gitignore").write_text("graphify-out/\n.project-memory/\n", encoding="utf-8")
            args = type("Args", (), {"project": project, "name": "Demo", "with_graphify": False})()
            with patch("graphify_project_memory.cli.print_json"):
                command_install(args)
            agents_after_first = (project / "AGENTS.md").read_bytes()
            with patch("graphify_project_memory.cli.print_json"):
                command_install(args)
            self.assertEqual(agents_after_first, (project / "AGENTS.md").read_bytes())
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(agents.count("<!-- project-memory:start -->"), 1)
            ignore = (project / ".gitignore").read_text(encoding="utf-8")
            self.assertNotIn("\ngraphify-out/\n", "\n" + ignore)
            self.assertNotIn("\n.project-memory/\n", "\n" + ignore)
            self.assertEqual(ignore.count("graphify-out/cache/"), 1)
            self.assertEqual(ignore.count(".project-memory/metrics.jsonl"), 1)
            graphifyignore = (project / ".graphifyignore").read_text(encoding="utf-8")
            self.assertEqual(graphifyignore.count(".project-memory/"), 1)
            self.assertEqual(graphifyignore.count("graphify-out/"), 1)
            self.assertTrue((project / "docs" / "project-memory" / "EVOLUTION.md").exists())

    def test_schema_two_migrates_without_losing_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            config = load_json(root / "config.json")
            config["schema_version"] = 2
            atomic_json(root / "config.json", config)
            (root / "graph-state.json").unlink()
            require_memory(project)
            self.assertEqual(load_json(root / "config.json")["schema_version"], SCHEMA_VERSION)
            self.assertTrue((root / "graph-state.json").exists())
            self.assertEqual(load_json(root / "config.json")["project_name"], project.name)

    def test_adaptive_query_uses_coverage_and_structure(self) -> None:
        memory = "Current task next action migration database"
        self.assertFalse(_needs_graph("What is the next action?", memory, 1.0))
        self.assertTrue(_needs_graph("Which function implements the API route?", memory, 1.0))
        self.assertTrue(_needs_graph("Tell me about deployment policy", memory, 0.1))
        self.assertEqual(_graph_escalation_reason("Which function implements the API route?", memory, 1.0), "structural_question")
        self.assertEqual(_graph_escalation_reason("deployment policy", memory, 0.1), "memory_coverage_low")

    def test_report_groups_metrics_sources_and_reduction_by_task(self) -> None:
        metrics = [
            {"task_id": "A", "baseline_tokens": 1000, "memory_tokens": 50, "graph_tokens": 100, "total_retrieval_tokens": 150, "quality": "correct", "expanded": True, "context_tier": "graph_expanded", "memory_coverage": 0.4, "escalation_reason": "memory_coverage_low"},
            {"task_id": "B", "baseline_tokens": 500, "memory_tokens": 20, "graph_tokens": 0, "total_retrieval_tokens": 20, "quality": "unrated", "expanded": False, "context_tier": "memory", "memory_coverage": 1.0},
        ]
        sources = [{"task_id": "A", "path": "src/a.py", "tokens": 50}]
        report = summarize(metrics, sources, "A")
        self.assertEqual(report["queries"], 1)
        self.assertEqual(report["source_tokens"], 50)
        self.assertEqual(report["retrieval_tokens"], 200)
        self.assertEqual(report["context_avoided_estimate"], 800)
        self.assertEqual(report["saved_tokens"], 800)
        self.assertEqual(report["adaptive_expansions"], 1)
        self.assertEqual(report["escalation_reasons"]["memory_coverage_low"], 1)

    def test_source_add_deduplicates_per_task_and_rejects_secret_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            source = project / "src.py"
            source.write_text("print('ok')\n", encoding="utf-8")
            args = type("Args", (), {"project": project, "task": "T1", "paths": [str(source)], "allow_sensitive": False})()
            with patch("graphify_project_memory.cli.print_json"):
                command_source_add(args)
                command_source_add(args)
            self.assertEqual(len(read_jsonl(root / "source-reads.jsonl")), 1)
            secret = project / ".env"
            secret.write_text("TOKEN=x\n", encoding="utf-8")
            secret_args = type("Args", (), {"project": project, "task": "T1", "paths": [str(secret)], "allow_sensitive": False})()
            with self.assertRaises(RuntimeError):
                command_source_add(secret_args)

    def test_freshness_detects_second_edit_when_git_status_text_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            root, _ = initialize(project)
            source_dir = project / "src"
            source_dir.mkdir()
            source = source_dir / "app.py"
            source.write_text("print('v1')\n", encoding="utf-8")
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            before_status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=project, text=True, capture_output=True, check=True).stdout
            source.write_text("print('v2')\n", encoding="utf-8")
            after_status = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=project, text=True, capture_output=True, check=True).stdout
            self.assertEqual(before_status, after_status)
            result = evaluate_freshness(project, root)
            self.assertFalse(result["fresh"])
            self.assertIn("working_tree_changed", result["reasons"])

    def test_memory_changes_do_not_change_working_tree_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            root, _ = initialize(project)
            source = project / "app.py"
            source.write_text("print('stable')\n", encoding="utf-8")
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            append_jsonl(root / "checkpoints.jsonl", {"summary": "memory-only change"})
            result = evaluate_freshness(project, root)
            self.assertTrue(result["fresh"])

    def test_freshness_baseline_detects_working_tree_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
            (graph_dir / "manifest.json").write_text('{}', encoding="utf-8")
            (project / "tracked.txt").write_text("one", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=project, check=True, capture_output=True)
            capture_graph_state(project, root, "0.9.57")
            self.assertTrue(evaluate_freshness(project, root)["fresh"])
            (project / "tracked.txt").write_text("two", encoding="utf-8")
            result = evaluate_freshness(project, root)
            self.assertFalse(result["fresh"])
            self.assertIn("working_tree_changed", result["reasons"])

    def test_graph_drift_without_source_change_is_warning_not_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            root, _ = initialize(project)
            source = project / "app.py"
            source.write_text("print('stable')\n", encoding="utf-8")
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            graph = graph_dir / "graph.json"
            manifest = graph_dir / "manifest.json"
            graph.write_text('{"nodes": []}', encoding="utf-8")
            manifest.write_text('{"files": []}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            graph.write_text('{"nodes": [{"id": "drift"}]}', encoding="utf-8")
            manifest.write_text('{"files": [], "drift": true}', encoding="utf-8")
            result = evaluate_freshness(project, root)
            self.assertTrue(result["fresh"])
            self.assertIn("graph_drift_without_source_change", result["warnings"])
            self.assertIn("manifest_drift_without_source_change", result["warnings"])

    def test_fingerprint_reports_nonzero_file_count_without_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            (project / "app.py").write_text("print('x')\n", encoding="utf-8")
            snapshot = git_snapshot(project)
            self.assertIsNotNone(snapshot["content_sha256"])
            self.assertGreater(snapshot["content_file_count"], 0)


    def test_schema_three_migrates_to_four_and_preserves_graph_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            config = load_json(root / "config.json")
            config["schema_version"] = 3
            atomic_json(root / "config.json", config)
            graph_state = {
                "schema_version": 3,
                "captured_at": "2026-01-01T00:00:00+00:00",
                "git": {"head": "abc123", "content_sha256": "sha", "content_file_count": 7},
            }
            atomic_json(root / "graph-state.json", graph_state)
            (root / "facts.jsonl").unlink(missing_ok=True)
            require_memory(project)
            migrated = load_json(root / "graph-state.json")
            self.assertEqual(load_json(root / "config.json")["schema_version"], 4)
            self.assertEqual(migrated["git"]["source_revision"], "abc123")
            self.assertEqual(migrated["git"]["observed_head"], "abc123")
            self.assertEqual(migrated["git"]["source_content_sha256"], "sha")
            self.assertTrue((root / "facts.jsonl").exists())

    def test_metadata_only_commit_keeps_source_fresh_and_source_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            source = project / "app.py"
            source.write_text("print('stable')\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "source"], cwd=project, check=True, capture_output=True)
            source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
            (graph_dir / "manifest.json").write_text('{}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            subprocess.run(["git", "add", ".project-memory", "graphify-out/graph.json", "graphify-out/manifest.json"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "metadata"], cwd=project, check=True, capture_output=True)
            metadata_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            self.assertNotEqual(source_head, metadata_head)
            result = evaluate_freshness(project, root)
            self.assertTrue(result["fresh"])
            self.assertIn("git_head_changed_without_source_change", result["warnings"])
            state = capture_graph_state(project, root, "0.9.57")
            self.assertEqual(state["git"]["source_revision"], source_head)
            self.assertEqual(state["git"]["observed_head"], metadata_head)

    def test_source_commit_change_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            source = project / "app.py"
            source.write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=project, check=True, capture_output=True)
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"; graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            source.write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "v2"], cwd=project, check=True, capture_output=True)
            result = evaluate_freshness(project, root)
            self.assertFalse(result["fresh"])
            self.assertIn("working_tree_changed", result["reasons"])
            self.assertIn("git_head_changed_with_source_change", result["reasons"])


    def test_agents_managed_block_change_does_not_change_source_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            agents = project / "AGENTS.md"
            agents.write_text(
                "# Human instructions\n\n<!-- project-memory:start -->\nold managed text\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "AGENTS.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=project, check=True, capture_output=True)
            before = working_tree_fingerprint(project)
            agents.write_text(
                "# Human instructions\n\n<!-- project-memory:start -->\nnew managed text\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            after = working_tree_fingerprint(project)
            self.assertEqual(before["content_sha256"], after["content_sha256"])
            snapshot = git_snapshot(project)
            self.assertFalse(snapshot["dirty"])
            self.assertIsNone(snapshot["status_hash"])

    def test_agents_human_change_outside_managed_block_is_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            agents = project / "AGENTS.md"
            agents.write_text(
                "# Human instructions\n\n<!-- project-memory:start -->\nmanaged\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "AGENTS.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=project, check=True, capture_output=True)
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"; graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            agents.write_text(
                "# Human instructions CHANGED\n\n<!-- project-memory:start -->\nmanaged v2\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            result = evaluate_freshness(project, root)
            self.assertFalse(result["fresh"])
            self.assertIn("working_tree_changed", result["reasons"])
            self.assertTrue(result["current"]["git"]["dirty"])

    def test_install_upgrades_legacy_fingerprint_after_metadata_only_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.py").write_text("print('stable')\n", encoding="utf-8")
            (project / "AGENTS.md").write_text(
                "# Human\n\n<!-- project-memory:start -->\nold managed text\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "app.py", "AGENTS.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "source"], cwd=project, check=True, capture_output=True)
            source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"; graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{}', encoding="utf-8")
            (graph_dir / "manifest.json").write_text('{}', encoding="utf-8")
            state = capture_graph_state(project, root, "0.9.57")
            # Simulate a 0.3.5/v1 graph-state while preserving the captured source revision.
            state["git"].pop("source_fingerprint_version", None)
            atomic_json(root / "graph-state.json", state)
            (root / "checkpoints.jsonl").write_text('{"summary":"metadata"}\n', encoding="utf-8")
            subprocess.run(["git", "add", ".project-memory", "graphify-out/graph.json", "graphify-out/manifest.json"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "metadata"], cwd=project, check=True, capture_output=True)
            metadata_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            # GPM updates only its managed AGENTS block in the working tree.
            (project / "AGENTS.md").write_text(
                "# Human\n\n<!-- project-memory:start -->\nnew managed text\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            migration = upgrade_graph_state_fingerprint(project, root)
            self.assertTrue(migration["changed"])
            migrated = load_json(root / "graph-state.json")
            self.assertEqual(migrated["git"]["source_revision"], source_head)
            self.assertEqual(migrated["git"]["observed_head"], metadata_head)
            self.assertEqual(migrated["git"]["source_fingerprint_version"], 2)
            result = evaluate_freshness(project, root)
            self.assertTrue(result["fresh"])
            self.assertEqual(result["current"]["git"]["effective_source_revision"], source_head)

    def test_install_upgrades_legacy_fingerprint_with_windows_crlf_managed_agents_change(self) -> None:
        """Regression for the 0.3.6 managed-AGENTS migration case on Windows."""
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            (project / "app.py").write_text("print('stable')\n", encoding="utf-8")
            agents = project / "AGENTS.md"
            agents.write_text(
                "# Human\n\n<!-- project-memory:start -->\nold managed text\n<!-- project-memory:end -->\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "app.py", "AGENTS.md"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "source"], cwd=project, check=True, capture_output=True)
            source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"; graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{}', encoding="utf-8")
            (graph_dir / "manifest.json").write_text('{}', encoding="utf-8")
            state = capture_graph_state(project, root, "0.9.57")
            state["git"].pop("source_fingerprint_version", None)
            atomic_json(root / "graph-state.json", state)
            (root / "checkpoints.jsonl").write_text('{"summary":"metadata"}\n', encoding="utf-8")
            subprocess.run(["git", "add", ".project-memory", "graphify-out/graph.json", "graphify-out/manifest.json"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "metadata"], cwd=project, check=True, capture_output=True)
            metadata_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()

            # Reproduce Windows checkout semantics: HEAD blob is LF, working tree is CRLF,
            # and only the GPM-managed block text changes. Also leave managed memory dirty.
            agents.write_bytes(
                b"# Human\r\n\r\n<!-- project-memory:start -->\r\nnew managed text\r\n<!-- project-memory:end -->\r\n"
            )
            config = load_json(root / "config.json")
            config["migration_probe"] = True
            atomic_json(root / "config.json", config)

            snap = git_snapshot(project)
            self.assertFalse(snap["dirty"])
            migration = upgrade_graph_state_fingerprint(project, root)
            self.assertTrue(migration["changed"], migration)
            migrated = load_json(root / "graph-state.json")
            self.assertEqual(migrated["git"]["source_revision"], source_head)
            self.assertEqual(migrated["git"]["observed_head"], metadata_head)
            self.assertEqual(migrated["git"]["source_fingerprint_version"], 2)
            result = evaluate_freshness(project, root)
            self.assertTrue(result["fresh"], result)
            self.assertEqual(result["current"]["git"]["effective_source_revision"], source_head)

    def test_legacy_fingerprint_upgrade_refuses_real_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            source = project / "app.py"
            source.write_text("v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "v1"], cwd=project, check=True, capture_output=True)
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"; graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{}', encoding="utf-8")
            state = capture_graph_state(project, root, "0.9.57")
            state["git"].pop("source_fingerprint_version", None)
            atomic_json(root / "graph-state.json", state)
            source.write_text("v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "v2"], cwd=project, check=True, capture_output=True)
            migration = upgrade_graph_state_fingerprint(project, root)
            self.assertFalse(migration["changed"])
            self.assertEqual(migration["reason"], "source_changed")


    def test_fact_provenance_uses_effective_source_revision_after_metadata_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            source = project / "app.py"
            source.write_text("print('stable')\n", encoding="utf-8")
            subprocess.run(["git", "add", "app.py"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "source"], cwd=project, check=True, capture_output=True)
            source_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            root, _ = initialize(project)
            graph_dir = project / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text('{"nodes": []}', encoding="utf-8")
            (graph_dir / "manifest.json").write_text('{}', encoding="utf-8")
            capture_graph_state(project, root, "0.9.57")
            subprocess.run(["git", "add", ".project-memory", "graphify-out/graph.json", "graphify-out/manifest.json"], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "metadata"], cwd=project, check=True, capture_output=True)
            metadata_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project, text=True, capture_output=True, check=True).stdout.strip()
            self.assertNotEqual(source_head, metadata_head)
            provenance = _provenance(project, "app.py", 1, 1)
            self.assertEqual(provenance["source_revision"], source_head)
            self.assertEqual(provenance["path"], "app.py")

    def test_reassert_same_fact_refreshes_provenance_without_new_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            first = add_fact(root, "queue", "mode", "fifo", {"source_revision": "old", "path": "app.py"}, 0.8)
            refreshed = add_fact(root, "queue", "mode", "fifo", {"source_revision": "new", "path": "app.py"}, 1.0)
            self.assertEqual(refreshed["fact_id"], first["fact_id"])
            self.assertEqual(refreshed["event"], "reassert")
            self.assertEqual(refreshed["provenance"]["source_revision"], "new")
            self.assertEqual(refreshed["confidence"], 1.0)
            latest = {item["fact_id"]: item for item in current_facts(root)}[first["fact_id"]]
            self.assertEqual(latest["provenance"]["source_revision"], "new")

    def test_fact_identity_supersession_and_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            first = add_fact(root, "queue", "mode", "fifo", {"source_type": "project_state"})
            duplicate = add_fact(root, "queue", "mode", "fifo", {"source_type": "project_state"})
            self.assertTrue(duplicate["duplicate"])
            second = add_fact(root, "queue", "mode", "priority", {"source_type": "project_state"})
            facts = {item["fact_id"]: item for item in current_facts(root)}
            self.assertEqual(facts[first["fact_id"]]["status"], "superseded")
            self.assertEqual(facts[first["fact_id"]]["superseded_by"], second["fact_id"])
            set_fact_status(root, second["fact_id"], "revoked", "invalidated by test")
            facts = {item["fact_id"]: item for item in current_facts(root)}
            self.assertEqual(facts[second["fact_id"]]["status"], "revoked")

    def test_fact_validation_marks_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            fact = add_fact(root, "module", "owner", "audio", {
                "source_type": "source_file", "path": "missing.py", "source_revision": "abc"
            })
            result = validate_facts(root, project, "abc")
            self.assertEqual(len(result["conflicts"]), 1)
            latest = {item["fact_id"]: item for item in current_facts(root)}[fact["fact_id"]]
            self.assertEqual(latest["status"], "needs_validation")

    def test_hydration_reads_only_narrow_graph_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            src = project / "app.py"
            src.write_text("\n".join(f"line{i}" for i in range(1, 51)) + "\n", encoding="utf-8")
            graph = "NODE demo() [src=app.py loc=L25 community=demo]"
            locations = graph_source_locations(graph)
            self.assertEqual(locations[0], {"path": "app.py", "line": 25})
            result = hydrate_sources(project, graph, radius=2, max_tokens=200)
            self.assertEqual(len(result["ranges"]), 1)
            self.assertEqual(result["ranges"][0]["start_line"], 23)
            self.assertEqual(result["ranges"][0]["end_line"], 27)
            self.assertIn("25: line25", result["text"])

    def test_consolidation_creates_summary_without_deleting_raw_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            root, _ = initialize(project)
            add_fact(root, "project", "phase", "testing", {"source_type": "project_state"})
            append_jsonl(root / "checkpoints.jsonl", {"timestamp": "now", "summary": "checkpoint raw"})
            before = (root / "checkpoints.jsonl").read_text(encoding="utf-8")
            result = consolidate(root)
            self.assertTrue(Path(result["target"]).exists())
            self.assertEqual((root / "checkpoints.jsonl").read_text(encoding="utf-8"), before)
            self.assertIn("Active facts", Path(result["target"]).read_text(encoding="utf-8"))

    def test_install_ignores_regenerable_graphify_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            args = type("Args", (), {"project": project, "name": "Demo", "with_graphify": False})()
            with patch("graphify_project_memory.cli.print_json"):
                command_install(args)
            ignore = (project / ".gitignore").read_text(encoding="utf-8")
            for expected in (
                "graphify-out/runtime/", "graphify-out/.vocab.txt", "graphify-out/before-*.json",
                "graphify-out/pre-graphify-*/", "graphify-out/graph.html",
            ):
                self.assertIn(expected, ignore)


if __name__ == "__main__":
    unittest.main()
