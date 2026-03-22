"""Tests for benchmark_cost CLI command."""

from __future__ import annotations

import json
import sqlite3

import pytest
from click.testing import CliRunner

from coderag.cli.benchmark_cost import (
    BUILTIN_PROMPTS,
    _estimate_with_coderag,
    _estimate_without_coderag,
    _get_codebase_stats,
    _render_markdown,
    _run_benchmark,
    benchmark,
)


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project with some source files."""
    # Create source files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    for i in range(10):
        f = src_dir / f"file_{i}.py"
        f.write_text(f"# File {i}\n" + "x = 1\n" * 50)

    # Create a nested dir
    nested = src_dir / "nested"
    nested.mkdir()
    (nested / "deep.py").write_text("def deep(): pass\n" * 20)

    return tmp_path


@pytest.fixture
def parsed_project(temp_project):
    """Create a temporary project with a mock .codegraph/graph.db."""
    codegraph_dir = temp_project / ".codegraph"
    codegraph_dir.mkdir()
    db_path = codegraph_dir / "graph.db"

    # Create minimal SQLite database that looks like a parsed project
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nodes "
        "(id TEXT PRIMARY KEY, name TEXT, kind TEXT, file_path TEXT, "
        "start_line INTEGER, end_line INTEGER, language TEXT, "
        "signature TEXT, docstring TEXT, metadata TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS edges "
        "(id INTEGER PRIMARY KEY, source_id TEXT, target_id TEXT, "
        "kind TEXT, metadata TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS project_summary (key TEXT PRIMARY KEY, value TEXT)")
    # Insert some nodes
    for i in range(5):
        conn.execute(
            "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"node_{i}",
                f"Symbol{i}",
                "function",
                f"src/file_{i}.py",
                1,
                10,
                "python",
                f"def symbol_{i}()",
                "",
                "{}",
            ),
        )
    conn.commit()
    conn.close()

    return temp_project


class TestGetCodebaseStats:
    """Tests for _get_codebase_stats."""

    def test_basic_stats(self, temp_project):
        stats = _get_codebase_stats(str(temp_project))
        assert stats["total_files"] > 0
        assert stats["total_size"] > 0
        assert stats["total_tokens"] > 0
        assert stats["avg_file_size"] > 0
        assert stats["avg_file_tokens"] > 0

    def test_skips_git_dir(self, temp_project):
        git_dir = temp_project / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")
        stats = _get_codebase_stats(str(temp_project))
        # .git files should not be counted
        assert stats["total_files"] == 11  # 10 + 1 nested

    def test_skips_node_modules(self, temp_project):
        nm_dir = temp_project / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "package.json").write_text("{}")
        stats = _get_codebase_stats(str(temp_project))
        assert stats["total_files"] == 11

    def test_empty_dir(self, tmp_path):
        stats = _get_codebase_stats(str(tmp_path))
        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        assert stats["avg_file_size"] == 0


class TestEstimateWithoutCoderag:
    """Tests for _estimate_without_coderag."""

    def test_grep_files_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("grep_files", stats)
        assert result > 0
        assert result == int(100 * 0.2 * 200)

    def test_read_file_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("read_file", stats)
        assert result == int(200 * 3)

    def test_grep_codebase_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("grep_codebase", stats)
        assert result == int(20000 * 0.3)

    def test_read_dependents_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("read_dependents", stats)
        assert result == int(200 * 5)

    def test_grep_routes_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("grep_routes", stats)
        assert result == int(100 * 0.15 * 200)

    def test_read_imports_strategy(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("read_imports", stats)
        assert result == int(200 * 4)

    def test_unknown_strategy_fallback(self):
        stats = {"total_files": 100, "avg_file_tokens": 200, "total_tokens": 20000}
        result = _estimate_without_coderag("unknown_strategy", stats)
        assert result == int(200 * 3)

    def test_minimum_100(self):
        stats = {"total_files": 1, "avg_file_tokens": 10, "total_tokens": 10}
        result = _estimate_without_coderag("grep_files", stats)
        assert result >= 100


class TestEstimateWithCoderag:
    """Tests for _estimate_with_coderag."""

    def test_no_db_returns_budget(self, tmp_path):
        result = _estimate_with_coderag("search", str(tmp_path), 4000)
        assert result == 4000

    def test_with_parsed_project(self, parsed_project):
        result = _estimate_with_coderag("search", str(parsed_project), 4000)
        assert result > 0
        assert result <= 4000


class TestRunBenchmark:
    """Tests for _run_benchmark."""

    def test_basic_benchmark(self, parsed_project):
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS, 4000)
        assert "project_name" in results
        assert "model" in results
        assert "summary" in results
        assert "tasks" in results
        assert len(results["tasks"]) == len(BUILTIN_PROMPTS)

    def test_summary_fields(self, parsed_project):
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS, 4000)
        summary = results["summary"]
        assert "num_tasks" in summary
        assert "avg_without_tokens" in summary
        assert "avg_with_tokens" in summary
        assert "total_without_tokens" in summary
        assert "total_with_tokens" in summary
        assert "savings_pct" in summary
        assert "context_hit_rate" in summary
        assert "without_cost" in summary
        assert "with_cost" in summary

    def test_task_fields(self, parsed_project):
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS[:1], 4000)
        task = results["tasks"][0]
        assert "task" in task
        assert "without_tokens" in task
        assert "with_tokens" in task
        assert "savings_pct" in task

    def test_different_models(self, parsed_project):
        results_sonnet = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS[:1], 4000)
        results_flash = _run_benchmark(str(parsed_project), "gemini-2.5-flash", BUILTIN_PROMPTS[:1], 4000)
        # Different models should produce different costs
        assert results_sonnet["summary"]["without_cost"] != results_flash["summary"]["without_cost"]

    def test_custom_prompts(self, parsed_project):
        custom = [
            {
                "task": "Custom task",
                "description": "A custom task",
                "without_strategy": "grep_files",
                "with_tool": "search",
            }
        ]
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", custom, 4000)
        assert len(results["tasks"]) == 1
        assert results["tasks"][0]["task"] == "Custom task"


class TestRenderMarkdown:
    """Tests for _render_markdown."""

    def test_produces_markdown(self, parsed_project):
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS, 4000)
        md = _render_markdown(results)
        assert "# CodeRAG Cost Benchmark" in md
        assert "## Summary" in md
        assert "## Per-Task Breakdown" in md
        assert "claude-sonnet-4" in md

    def test_contains_table_headers(self, parsed_project):
        results = _run_benchmark(str(parsed_project), "claude-sonnet-4", BUILTIN_PROMPTS, 4000)
        md = _render_markdown(results)
        assert "| Metric |" in md
        assert "| Task |" in md


class TestBenchmarkCLI:
    """Tests for the benchmark CLI command."""

    def test_no_parsed_project(self, temp_project):
        runner = CliRunner()
        result = runner.invoke(benchmark, [str(temp_project)])
        assert result.exit_code != 0
        assert "No parsed project" in result.output or "Error" in result.output

    def test_unknown_model(self, parsed_project):
        runner = CliRunner()
        result = runner.invoke(benchmark, [str(parsed_project), "--model", "nonexistent-model"])
        assert result.exit_code != 0

    def test_table_format(self, parsed_project):
        runner = CliRunner()
        result = runner.invoke(benchmark, [str(parsed_project), "--format", "table"])
        assert result.exit_code == 0

    def test_json_format(self, parsed_project):
        runner = CliRunner()
        result = runner.invoke(benchmark, [str(parsed_project), "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "tasks" in data
        assert "summary" in data

    def test_markdown_format(self, parsed_project):
        runner = CliRunner()
        result = runner.invoke(benchmark, [str(parsed_project), "--format", "markdown"])
        assert result.exit_code == 0
        assert "# CodeRAG Cost Benchmark" in result.output

    def test_json_output_file(self, parsed_project, tmp_path):
        output_file = tmp_path / "results.json"
        runner = CliRunner()
        result = runner.invoke(
            benchmark,
            [
                str(parsed_project),
                "--format",
                "json",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "tasks" in data

    def test_markdown_output_file(self, parsed_project, tmp_path):
        output_file = tmp_path / "results.md"
        runner = CliRunner()
        result = runner.invoke(
            benchmark,
            [
                str(parsed_project),
                "--format",
                "markdown",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        assert "# CodeRAG Cost Benchmark" in output_file.read_text()

    def test_custom_prompts_file(self, parsed_project, tmp_path):
        prompts_file = tmp_path / "prompts.json"
        prompts_file.write_text(
            json.dumps(
                [
                    {
                        "task": "Custom",
                        "description": "Test",
                        "without_strategy": "grep_files",
                        "with_tool": "search",
                    }
                ]
            )
        )
        runner = CliRunner()
        result = runner.invoke(
            benchmark,
            [
                str(parsed_project),
                "--format",
                "json",
                "--prompts",
                str(prompts_file),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task"] == "Custom"

    def test_custom_token_budget(self, parsed_project):
        runner = CliRunner()
        result = runner.invoke(
            benchmark,
            [
                str(parsed_project),
                "--format",
                "json",
                "--token-budget",
                "2000",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["token_budget"] == 2000

    def test_table_with_output_saves_json(self, parsed_project, tmp_path):
        output_file = tmp_path / "results.json"
        runner = CliRunner()
        result = runner.invoke(
            benchmark,
            [
                str(parsed_project),
                "--format",
                "table",
                "--output",
                str(output_file),
            ],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "tasks" in data
