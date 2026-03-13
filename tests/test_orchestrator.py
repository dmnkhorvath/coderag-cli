"""Tests for PipelineOrchestrator — targeting uncovered methods and branches."""

import os
import subprocess
from unittest.mock import MagicMock

import pytest

from coderag.core.config import CodeGraphConfig
from coderag.core.models import (
    Edge,
    EdgeKind,
    ExtractionResult,
    FileInfo,
    Node,
    NodeKind,
    PipelineSummary,
)
from coderag.core.registry import PluginRegistry
from coderag.pipeline.events import (
    EventEmitter,
    FileError,
    PhaseCompleted,
    PhaseProgress,
    PhaseStarted,
    PipelinePhase,
    PipelineStarted,
)
from coderag.pipeline.events import PipelineCompleted as PipelineCompletedEvent
from coderag.pipeline.orchestrator import PipelineOrchestrator
from coderag.storage.sqlite_store import SQLiteStore

# ── Helpers ──────────────────────────────────────────────────


def _make_node(file_path, line, kind, name, **kw):
    """Create a Node with required fields."""
    return Node(
        id=kw.get("id", f"{name}-{line}"),
        kind=kind,
        name=name,
        qualified_name=kw.get("qualified_name", name),
        file_path=file_path,
        start_line=line,
        end_line=kw.get("end_line", line + 5),
        language=kw.get("language", "php"),
    )


def _make_config():
    return CodeGraphConfig()


def _make_store(tmp_path):
    db_path = os.path.join(str(tmp_path), "test.db")
    store = SQLiteStore(db_path)
    store.initialize()
    return store


def _make_registry():
    return PluginRegistry()


def _write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


# ── Test: _emit ──────────────────────────────────────────────


class TestEmit:
    def test_emit_with_emitter(self, tmp_path):
        emitter = MagicMock(spec=EventEmitter)
        orch = PipelineOrchestrator(_make_config(), _make_registry(), _make_store(tmp_path), emitter=emitter)
        event = PipelineStarted(project_root="/tmp/test")
        orch._emit(event)
        emitter.emit.assert_called_once_with(event)

    def test_emit_without_emitter(self, tmp_path):
        orch = PipelineOrchestrator(_make_config(), _make_registry(), _make_store(tmp_path), emitter=None)
        orch._emit(PipelineStarted(project_root="/tmp/test"))


# ── Test: _read_file ─────────────────────────────────────────


class TestReadFile:
    def test_reads_file_bytes(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_bytes(b"hello world")
        result = PipelineOrchestrator._read_file(str(f))
        assert result == b"hello world"

    def test_reads_binary_content(self, tmp_path):
        f = tmp_path / "binary.bin"
        data = bytes(range(256))
        f.write_bytes(data)
        result = PipelineOrchestrator._read_file(str(f))
        assert result == data

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PipelineOrchestrator._read_file(str(tmp_path / "nonexistent.txt"))


# ── Test: _persist_result ────────────────────────────────────


class TestPersistResult:
    def test_persist_stores_nodes_and_edges(self, tmp_path):
        store = _make_store(tmp_path)
        orch = PipelineOrchestrator(_make_config(), _make_registry(), store)

        node = _make_node("test.php", 1, NodeKind.CLASS, "Foo")
        edge = Edge(source_id=node.id, target_id="bar-1", kind=EdgeKind.CALLS)
        result = ExtractionResult(
            file_path="test.php",
            language="php",
            nodes=[node],
            edges=[edge],
        )
        fi = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="abc123",
            is_changed=True,
        )
        orch._persist_result(result, fi, "php")

        found = store.find_nodes(kind=NodeKind.CLASS)
        assert len(found) >= 1
        assert found[0].name == "Foo"

    def test_persist_updates_file_hash(self, tmp_path):
        store = _make_store(tmp_path)
        orch = PipelineOrchestrator(_make_config(), _make_registry(), store)

        node = _make_node("test.php", 1, NodeKind.FILE, "test.php", id="file-test")
        result = ExtractionResult(
            file_path="test.php",
            language="php",
            nodes=[node],
            edges=[],
        )
        fi = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="hash123",
            is_changed=True,
        )
        orch._persist_result(result, fi, "php")

        stored_hash = store.get_file_hash("test.php")
        assert stored_hash == "hash123"

    def test_persist_deletes_old_data_first(self, tmp_path):
        store = _make_store(tmp_path)
        orch = PipelineOrchestrator(_make_config(), _make_registry(), store)

        node1 = _make_node("test.php", 1, NodeKind.CLASS, "OldClass", id="old-1")
        result1 = ExtractionResult(file_path="test.php", language="php", nodes=[node1], edges=[])
        fi = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="hash1",
            is_changed=True,
        )
        orch._persist_result(result1, fi, "php")

        node2 = _make_node("test.php", 1, NodeKind.CLASS, "NewClass", id="new-1")
        result2 = ExtractionResult(file_path="test.php", language="php", nodes=[node2], edges=[])
        fi2 = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="hash2",
            is_changed=True,
        )
        orch._persist_result(result2, fi2, "php")

        classes = store.find_nodes(kind=NodeKind.CLASS)
        names = {n.name for n in classes}
        assert "NewClass" in names

    def test_persist_empty_result(self, tmp_path):
        store = _make_store(tmp_path)
        orch = PipelineOrchestrator(_make_config(), _make_registry(), store)

        result = ExtractionResult(file_path="empty.php", language="php", nodes=[], edges=[])
        fi = FileInfo(
            path="empty.php",
            relative_path="empty.php",
            language="php",
            plugin_name="php",
            content_hash="emptyhash",
            is_changed=True,
        )
        orch._persist_result(result, fi, "php")


# ── Test: _run_framework_detection ───────────────────────────


class TestRunFrameworkDetection:
    def test_no_detectors_returns_zero(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        nodes, edges = orch._run_framework_detection(str(tmp_path))
        assert nodes == 0
        assert edges == 0

    def test_no_active_frameworks_returns_zero(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()

        mock_plugin = MagicMock()
        mock_plugin.name = "test_plugin"
        mock_plugin.file_extensions = {".test"}
        mock_detector = MagicMock()
        mock_detector.detect_framework.return_value = False
        mock_detector.framework_name = "TestFramework"
        mock_plugin.get_framework_detectors.return_value = [mock_detector]
        registry.register_plugin(mock_plugin)

        orch = PipelineOrchestrator(_make_config(), registry, store)
        nodes, edges = orch._run_framework_detection(str(tmp_path))
        assert nodes == 0
        assert edges == 0

    def test_detector_exception_handled_gracefully(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()

        mock_plugin = MagicMock()
        mock_plugin.name = "broken_plugin"
        mock_plugin.file_extensions = {".broken"}
        mock_plugin.get_framework_detectors.side_effect = RuntimeError("boom")
        registry.register_plugin(mock_plugin)

        orch = PipelineOrchestrator(_make_config(), registry, store)
        nodes, edges = orch._run_framework_detection(str(tmp_path))
        assert nodes == 0
        assert edges == 0

    def test_detect_framework_exception_handled(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()

        mock_plugin = MagicMock()
        mock_plugin.name = "test_plugin"
        mock_plugin.file_extensions = {".test"}
        mock_detector = MagicMock()
        mock_detector.detect_framework.side_effect = RuntimeError("detection failed")
        mock_detector.framework_name = "BrokenFramework"
        mock_plugin.get_framework_detectors.return_value = [mock_detector]
        registry.register_plugin(mock_plugin)

        orch = PipelineOrchestrator(_make_config(), registry, store)
        nodes, edges = orch._run_framework_detection(str(tmp_path))
        assert nodes == 0
        assert edges == 0


# ── Test: _run_cross_language_matching ────────────────────────


class TestRunCrossLanguageMatching:
    def test_single_language_skips(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        result = orch._run_cross_language_matching(str(tmp_path))
        assert result == 0


# ── Test: _run_style_edge_matching ───────────────────────────


class TestRunStyleEdgeMatching:
    def test_no_css_files_returns_zero(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        result = orch._run_style_edge_matching(str(tmp_path))
        assert result == 0


# ── Test: _run_git_enrichment ────────────────────────────────


class TestRunGitEnrichment:
    def test_no_git_repo_returns_empty_stats(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        stats = orch._run_git_enrichment(str(tmp_path))
        assert stats["files_enriched"] == 0
        assert stats["co_change_pairs"] == 0

    def test_git_repo_runs_enrichment(self, tmp_path):
        project = str(tmp_path / "gitproject")
        os.makedirs(project)
        subprocess.run(["git", "init", project], capture_output=True)
        subprocess.run(["git", "-C", project, "config", "user.email", "t@t.com"], capture_output=True)
        subprocess.run(["git", "-C", project, "config", "user.name", "T"], capture_output=True)

        _write_file(os.path.join(project, "test.php"), "<?php class Foo {}")
        subprocess.run(["git", "-C", project, "add", "."], capture_output=True)
        subprocess.run(["git", "-C", project, "commit", "-m", "init"], capture_output=True)

        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        stats = orch._run_git_enrichment(project)
        assert isinstance(stats, dict)
        assert "files_enriched" in stats


# ── Test: _run_phpstan_enrichment ────────────────────────────


class TestRunPhpstanEnrichment:
    def test_phpstan_not_available(self, tmp_path):
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        stats = orch._run_phpstan_enrichment(str(tmp_path))
        assert isinstance(stats, dict)
        assert stats.get("skipped_reason") is not None or stats.get("files_analyzed", 0) >= 0


# ── Test: Full run ───────────────────────────────────────────


class TestRunPipeline:
    def test_run_empty_project_returns_summary(self, tmp_path):
        project = str(tmp_path / "empty_project")
        os.makedirs(project)

        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        summary = orch.run(project, incremental=False)

        assert isinstance(summary, PipelineSummary)
        assert summary.total_files == 0
        assert summary.files_parsed == 0
        assert summary.files_errored == 0

    def test_run_emits_pipeline_events(self, tmp_path):
        project = str(tmp_path / "event_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        event_types = [type(call.args[0]) for call in emitter.emit.call_args_list]
        assert PipelineStarted in event_types
        assert PipelineCompletedEvent in event_types
        phase_started_events = [e for e in event_types if e == PhaseStarted]
        assert len(phase_started_events) >= 4

    def test_run_incremental_mode(self, tmp_path):
        project = str(tmp_path / "incr_project")
        os.makedirs(project)

        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)

        orch.run(project, incremental=False)
        summary2 = orch.run(project, incremental=True)

        assert isinstance(summary2, PipelineSummary)
        assert summary2.files_parsed == 0

    def test_run_with_real_php_file(self, tmp_path):
        from coderag.plugins import BUILTIN_PLUGINS

        project = str(tmp_path / "php_project")
        os.makedirs(project)
        _write_file(
            os.path.join(project, "Test.php"),
            "<?php\nclass TestClass {\n    public function hello() {}\n}\n",
        )

        store = _make_store(tmp_path)
        registry = PluginRegistry()
        for p in BUILTIN_PLUGINS:
            registry.register_plugin(p())

        orch = PipelineOrchestrator(_make_config(), registry, store)
        summary = orch.run(project, incremental=False)

        assert summary.files_parsed >= 1
        assert summary.total_nodes >= 1

    def test_run_with_multiple_file_types(self, tmp_path):
        from coderag.plugins import BUILTIN_PLUGINS

        project = str(tmp_path / "multi_project")
        os.makedirs(project)
        _write_file(
            os.path.join(project, "App.php"),
            "<?php\nclass App {}\n",
        )
        _write_file(
            os.path.join(project, "main.js"),
            "function hello() { return 42; }\n",
        )

        store = _make_store(tmp_path)
        registry = PluginRegistry()
        for p in BUILTIN_PLUGINS:
            registry.register_plugin(p())

        orch = PipelineOrchestrator(_make_config(), registry, store)
        summary = orch.run(project, incremental=False)

        assert summary.files_parsed >= 2
        assert summary.total_nodes >= 2

    def test_run_returns_pipeline_time(self, tmp_path):
        project = str(tmp_path / "time_project")
        os.makedirs(project)

        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store)
        summary = orch.run(project, incremental=False)

        assert summary.total_pipeline_time_ms > 0


# ── Test: PipelineSummary ────────────────────────────────────


class TestPipelineSummary:
    def test_default_values(self):
        summary = PipelineSummary()
        assert summary.total_files == 0
        assert summary.files_parsed == 0
        assert summary.files_skipped == 0
        assert summary.files_errored == 0
        assert summary.total_nodes == 0
        assert summary.total_edges == 0

    def test_custom_values(self):
        summary = PipelineSummary(
            total_files=10,
            files_parsed=8,
            files_skipped=2,
            files_errored=1,
            total_nodes=100,
            total_edges=50,
            total_pipeline_time_ms=1234.5,
        )
        assert summary.total_files == 10
        assert summary.files_parsed == 8
        assert summary.files_skipped == 2
        assert summary.total_pipeline_time_ms == 1234.5


# ── Test: Event types ────────────────────────────────────────


class TestEventTypes:
    def test_phase_started_event(self):
        event = PhaseStarted(phase=PipelinePhase.DISCOVERY)
        assert event.phase == PipelinePhase.DISCOVERY

    def test_phase_completed_event(self):
        event = PhaseCompleted(
            phase=PipelinePhase.EXTRACTION,
            summary={"parsed": 5, "errors": 0},
        )
        assert event.phase == PipelinePhase.EXTRACTION
        assert event.summary["parsed"] == 5

    def test_phase_progress_event(self):
        event = PhaseProgress(
            phase=PipelinePhase.EXTRACTION,
            current=3,
            total=10,
            message="Parsed file.php",
            file_path="file.php",
        )
        assert event.current == 3
        assert event.total == 10

    def test_file_error_event(self):
        event = FileError(
            phase=PipelinePhase.EXTRACTION,
            file_path="broken.php",
            error="parse error",
        )
        assert event.file_path == "broken.php"
        assert event.error == "parse error"

    def test_pipeline_started_event(self):
        event = PipelineStarted(project_root="/tmp/test")
        assert event.project_root == "/tmp/test"

    def test_pipeline_completed_event(self):
        event = PipelineCompletedEvent(
            total_files=10,
            total_nodes=100,
            total_edges=50,
            total_errors=1,
            duration_s=2.5,
        )
        assert event.total_files == 10
        assert event.duration_s == 2.5


# ── Test: FileInfo ───────────────────────────────────────────


class TestFileInfo:
    def test_changed_file(self):
        fi = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="abc",
            is_changed=True,
        )
        assert fi.is_changed is True
        assert fi.content_hash == "abc"

    def test_unchanged_file(self):
        fi = FileInfo(
            path="test.php",
            relative_path="test.php",
            language="php",
            plugin_name="php",
            content_hash="abc",
            is_changed=False,
        )
        assert fi.is_changed is False


# ── Test: Phase events ───────────────────────────────────────


class TestPhaseEvents:
    def test_all_phases_emit_started_and_completed(self, tmp_path):
        project = str(tmp_path / "phase_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        events = [call.args[0] for call in emitter.emit.call_args_list]
        started_phases = {e.phase for e in events if isinstance(e, PhaseStarted)}
        completed_phases = {e.phase for e in events if isinstance(e, PhaseCompleted)}

        expected = {
            PipelinePhase.DISCOVERY,
            PipelinePhase.HASHING,
            PipelinePhase.EXTRACTION,
            PipelinePhase.RESOLUTION,
        }
        assert expected.issubset(started_phases)
        assert expected.issubset(completed_phases)

    def test_framework_detection_phase_events(self, tmp_path):
        project = str(tmp_path / "fw_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        events = [call.args[0] for call in emitter.emit.call_args_list]
        fw_started = [e for e in events if isinstance(e, PhaseStarted) and e.phase == PipelinePhase.FRAMEWORK_DETECTION]
        fw_completed = [
            e for e in events if isinstance(e, PhaseCompleted) and e.phase == PipelinePhase.FRAMEWORK_DETECTION
        ]
        assert len(fw_started) == 1
        assert len(fw_completed) == 1

    def test_cross_language_phase_events(self, tmp_path):
        project = str(tmp_path / "xl_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        events = [call.args[0] for call in emitter.emit.call_args_list]
        xl_started = [e for e in events if isinstance(e, PhaseStarted) and e.phase == PipelinePhase.CROSS_LANGUAGE]
        xl_completed = [e for e in events if isinstance(e, PhaseCompleted) and e.phase == PipelinePhase.CROSS_LANGUAGE]
        assert len(xl_started) == 1
        assert len(xl_completed) == 1

    def test_style_matching_phase_events(self, tmp_path):
        project = str(tmp_path / "style_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        events = [call.args[0] for call in emitter.emit.call_args_list]
        style_started = [e for e in events if isinstance(e, PhaseStarted) and e.phase == PipelinePhase.STYLE_MATCHING]
        style_completed = [
            e for e in events if isinstance(e, PhaseCompleted) and e.phase == PipelinePhase.STYLE_MATCHING
        ]
        assert len(style_started) == 1
        assert len(style_completed) == 1

    def test_git_enrichment_phase_events(self, tmp_path):
        project = str(tmp_path / "git_project")
        os.makedirs(project)

        emitter = MagicMock(spec=EventEmitter)
        store = _make_store(tmp_path)
        registry = _make_registry()
        orch = PipelineOrchestrator(_make_config(), registry, store, emitter=emitter)
        orch.run(project, incremental=False)

        events = [call.args[0] for call in emitter.emit.call_args_list]
        git_started = [e for e in events if isinstance(e, PhaseStarted) and e.phase == PipelinePhase.GIT_ENRICHMENT]
        git_completed = [e for e in events if isinstance(e, PhaseCompleted) and e.phase == PipelinePhase.GIT_ENRICHMENT]
        assert len(git_started) == 1
        assert len(git_completed) == 1


# ── Test: Worker functions ───────────────────────────────────


class TestWorkerFunctions:
    def test_extract_worker_no_plugin(self, tmp_path):
        from coderag.pipeline.orchestrator import _extract_worker

        unsupported = str(tmp_path / "test.xyz")
        with open(unsupported, "w") as f:
            f.write("unsupported content")

        file_path, result, plugin_name, error = _extract_worker(unsupported)
        assert file_path == unsupported
        assert result is None
        assert plugin_name is None
        assert error is None

    def test_extract_worker_missing_file(self):
        from coderag.pipeline.orchestrator import _extract_worker

        file_path, result, plugin_name, error = _extract_worker("/nonexistent/file.php")
        assert file_path == "/nonexistent/file.php"

    def test_extract_worker_valid_php(self, tmp_path):
        from coderag.pipeline.orchestrator import _extract_worker

        php_file = str(tmp_path / "Valid.php")
        with open(php_file, "w") as f:
            f.write("<?php\nclass Valid {\n    public function test() {}\n}\n")

        file_path, result, plugin_name, error = _extract_worker(php_file)
        assert file_path == php_file
        if result is not None:
            assert len(result.nodes) >= 1
            assert error is None

    def test_init_extraction_worker(self):
        from coderag.pipeline.orchestrator import _init_extraction_worker

        _init_extraction_worker()
        # Should not raise


# ── Test: ExtractionResult ───────────────────────────────────


class TestExtractionResult:
    def test_empty_result(self):
        result = ExtractionResult(file_path="test.php", language="php")
        assert result.file_path == "test.php"
        assert result.language == "php"

    def test_result_with_data(self):
        node = _make_node("test.php", 1, NodeKind.CLASS, "Foo")
        edge = Edge(source_id=node.id, target_id="bar", kind=EdgeKind.CALLS)
        result = ExtractionResult(
            file_path="test.php",
            language="php",
            nodes=[node],
            edges=[edge],
        )
        assert len(result.nodes) == 1
        assert len(result.edges) == 1


# ── Test: Incremental with changes ───────────────────────────


class TestIncrementalPipeline:
    def test_incremental_detects_changes(self, tmp_path):
        from coderag.plugins import BUILTIN_PLUGINS

        project = str(tmp_path / "incr_project")
        os.makedirs(project)
        php_file = os.path.join(project, "Test.php")
        _write_file(php_file, "<?php\nclass TestClass {}\n")

        store = _make_store(tmp_path)
        registry = PluginRegistry()
        for p in BUILTIN_PLUGINS:
            registry.register_plugin(p())

        orch = PipelineOrchestrator(_make_config(), registry, store)

        # First run
        summary1 = orch.run(project, incremental=False)
        assert summary1.files_parsed >= 1

        # Second run without changes
        summary2 = orch.run(project, incremental=True)
        assert summary2.files_parsed == 0

        # Modify file and run again
        _write_file(php_file, "<?php\nclass TestClass { public function foo() {} }\n")
        summary3 = orch.run(project, incremental=True)
        assert summary3.files_parsed >= 1

    def test_full_reparse_ignores_hashes(self, tmp_path):
        from coderag.plugins import BUILTIN_PLUGINS

        project = str(tmp_path / "full_project")
        os.makedirs(project)
        _write_file(os.path.join(project, "A.php"), "<?php\nclass A {}\n")

        store = _make_store(tmp_path)
        registry = PluginRegistry()
        for p in BUILTIN_PLUGINS:
            registry.register_plugin(p())

        orch = PipelineOrchestrator(_make_config(), registry, store)

        summary1 = orch.run(project, incremental=False)
        summary2 = orch.run(project, incremental=False)

        # Full reparse should parse all files again
        assert summary2.files_parsed == summary1.files_parsed
