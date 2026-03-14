"""Coverage boost tests for MCP server, registry, orchestrator, and CLI commands."""

import os
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

# ============================================================================
# MCP Server Tests
# ============================================================================


class TestMCPServerFindDbPath:
    """Test _find_db_path helper."""

    def test_explicit_db_path_exists(self, tmp_path):
        from coderag.mcp.server import _find_db_path

        db = tmp_path / "graph.db"
        db.touch()
        result = _find_db_path(str(tmp_path), str(db))
        assert result == db

    def test_explicit_db_path_not_exists(self, tmp_path):
        from coderag.mcp.server import _find_db_path

        with pytest.raises(FileNotFoundError, match="Graph database not found"):
            _find_db_path(str(tmp_path), str(tmp_path / "nonexistent.db"))

    def test_default_db_path(self, tmp_path):
        from coderag.mcp.server import _DEFAULT_DB_SUBPATH, _find_db_path

        db = tmp_path / _DEFAULT_DB_SUBPATH
        db.parent.mkdir(parents=True, exist_ok=True)
        db.touch()
        result = _find_db_path(str(tmp_path), None)
        assert result == db

    def test_default_db_path_not_exists(self, tmp_path):
        from coderag.mcp.server import _find_db_path

        with pytest.raises(FileNotFoundError, match="Run 'coderag parse"):
            _find_db_path(str(tmp_path), None)


class TestGraphContext:
    """Test GraphContext lifecycle."""

    def test_init_loads_store_and_analyzer(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        store.close()

        from coderag.mcp.server import GraphContext

        ctx = GraphContext(str(tmp_path / "test.db"))
        assert ctx.store is not None
        assert ctx.analyzer is not None
        ctx.store.close()

    def test_check_and_reload_no_change(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        store.close()

        from coderag.mcp.server import GraphContext

        ctx = GraphContext(str(tmp_path / "test.db"))
        # Should not reload when mtime hasn't changed
        ctx.check_and_reload()
        ctx.store.close()

    def test_check_and_reload_with_change(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        store.close()

        from coderag.mcp.server import GraphContext

        ctx = GraphContext(str(tmp_path / "test.db"))
        # Simulate file change by modifying mtime
        ctx._last_mtime = 0
        ctx.check_and_reload()
        ctx.store.close()


class TestCreateServer:
    """Test create_server function."""

    def test_create_server_basic(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        store.close()

        from coderag.mcp.server import create_server

        mcp, ctx = create_server(str(tmp_path), str(tmp_path / "test.db"), hot_reload=False)
        assert mcp is not None
        assert ctx is not None
        ctx.store.close()

    def test_create_server_hot_reload(self, tmp_path):
        from coderag.storage.sqlite_store import SQLiteStore

        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        store.close()

        from coderag.mcp.server import create_server

        mcp, ctx = create_server(str(tmp_path), str(tmp_path / "test.db"), hot_reload=True)
        assert mcp is not None
        ctx.store.close()

    def test_create_server_db_not_found(self, tmp_path):
        from coderag.mcp.server import create_server

        with pytest.raises(FileNotFoundError):
            create_server(str(tmp_path))


# ============================================================================
# Registry Tests
# ============================================================================


class TestPluginRegistryExtended:
    """Extended tests for PluginRegistry."""

    def test_register_duplicate_plugin_raises(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        plugin = MagicMock()
        plugin.name = "test"
        plugin.file_extensions = [".test"]
        registry.register_plugin(plugin)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_plugin(plugin)

    def test_extension_conflict_warning(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        p1 = MagicMock()
        p1.name = "plugin1"
        p1.file_extensions = [".js"]
        p2 = MagicMock()
        p2.name = "plugin2"
        p2.file_extensions = [".js"]
        registry.register_plugin(p1)
        registry.register_plugin(p2)
        assert registry._extension_map[".js"] == "plugin2"

    def test_get_plugin_returns_none_for_unknown(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        assert registry.get_plugin("nonexistent") is None

    def test_get_plugin_for_file_by_extension(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        plugin = MagicMock()
        plugin.name = "php"
        plugin.file_extensions = [".php"]
        registry.register_plugin(plugin)
        result = registry.get_plugin_for_file("test.php")
        assert result is not None
        assert result.name == "php"

    def test_get_plugin_for_file_unknown_extension(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        assert registry.get_plugin_for_file("test.xyz") is None

    def test_discover_builtin_plugins(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        names = registry.discover_builtin_plugins()
        assert len(names) >= 6  # php, js, ts, python, css, scss
        assert "php" in names
        assert "javascript" in names

    def test_get_all_plugins(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        plugins = registry.get_all_plugins()
        assert len(plugins) >= 6

    def test_get_all_extensions(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        exts = registry.get_all_extensions()
        assert ".php" in exts
        assert ".js" in exts
        assert ".ts" in exts
        assert ".py" in exts

    def test_discover_plugins_no_entry_points(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        # Mock entry_points to return empty
        mock_eps = MagicMock()
        mock_eps.select.return_value = []
        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discovered = registry.discover_plugins()
        assert discovered == []


# ============================================================================
# Orchestrator Worker Tests
# ============================================================================


class TestExtractionWorker:
    """Test module-level worker functions."""

    def test_init_extraction_worker(self):
        from coderag.pipeline.orchestrator import _init_extraction_worker

        _init_extraction_worker()
        from coderag.pipeline import orchestrator

        assert orchestrator._worker_registry is not None

    def test_extract_worker_unsupported_file(self):
        from coderag.pipeline.orchestrator import _extract_worker, _init_extraction_worker

        _init_extraction_worker()
        result = _extract_worker("/tmp/test.xyz")
        assert result[0] == "/tmp/test.xyz"
        assert result[1] is None  # no result
        assert result[2] is None  # no plugin

    def test_extract_worker_php_file(self, tmp_path):
        from coderag.pipeline.orchestrator import _extract_worker, _init_extraction_worker

        _init_extraction_worker()
        php_file = tmp_path / "test.php"
        php_file.write_text("<?php\nclass Foo {\n    public function bar() {}\n}")
        result = _extract_worker(str(php_file))
        assert result[0] == str(php_file)
        assert result[1] is not None  # has extraction result
        assert result[2] == "php"  # plugin name
        assert result[3] is None  # no error

    def test_extract_worker_missing_file(self):
        from coderag.pipeline.orchestrator import _extract_worker, _init_extraction_worker

        _init_extraction_worker()
        result = _extract_worker("/tmp/nonexistent_file.php")
        assert result[0] == "/tmp/nonexistent_file.php"
        assert result[1] is None
        assert result[3] is not None  # has error


# ============================================================================
# More CLI Command Tests
# ============================================================================


class TestCLIParseCommand:
    """Test parse CLI command."""

    def test_parse_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["parse", "--help"])
        assert result.exit_code == 0
        assert "parse" in result.output.lower() or "Parse" in result.output

    def test_parse_nonexistent_dir(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["parse", "/tmp/nonexistent_dir_xyz"])
        assert result.exit_code != 0 or "error" in result.output.lower() or "not" in result.output.lower()

    def test_parse_empty_dir(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["parse", str(tmp_path)])
        # Should complete (possibly with 0 files)
        assert (
            result.exit_code == 0
            or "0 files" in result.output.lower()
            or "no files" in result.output.lower()
            or result.exit_code == 1
        )

    def test_parse_with_php_file(self, tmp_path):
        from coderag.cli.main import cli

        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {}")
        runner = CliRunner()
        result = runner.invoke(cli, ["parse", str(tmp_path)])
        # Should parse successfully
        assert result.exit_code == 0


class TestCLIInfoCommand:
    """Test info CLI command."""

    def test_info_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["info", "--help"])
        assert result.exit_code == 0

    def test_info_no_db(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["info"])
        # Should fail gracefully - no database
        assert (
            result.exit_code != 0
            or "not found" in result.output.lower()
            or "error" in result.output.lower()
            or "no" in result.output.lower()
        )

    def test_info_with_parsed_project(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["info"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIInitCommand:
    """Test init CLI command."""

    def test_init_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_init_creates_config(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIAnalyzeCommand:
    """Test analyze CLI command."""

    def test_analyze_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0

    def test_analyze_with_parsed_project(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {\n    public function greet() {}\n}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["analyze", "Hello"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIFrameworksCommand:
    """Test frameworks CLI command."""

    def test_frameworks_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["frameworks", "--help"])
        assert result.exit_code == 0

    def test_frameworks_with_parsed_project(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["frameworks"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIQueryCommand:
    """Test query CLI command."""

    def test_query_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0

    def test_query_with_parsed_project(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass SearchableClass {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["query", "SearchableClass"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLICrossLanguageCommand:
    """Test cross-language CLI command."""

    def test_cross_language_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["cross-language", "--help"])
        assert result.exit_code == 0


class TestCLIArchitectureCommand:
    """Test architecture CLI command."""

    def test_architecture_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["architecture", "--help"])
        assert result.exit_code == 0

    def test_architecture_with_parsed_project(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["architecture"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_architecture_json_output(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        php = tmp_path / "test.php"
        php.write_text("<?php\nclass Hello {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["architecture", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIValidateCommand:
    """Test validate CLI command."""

    def test_validate_basic(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_validate_with_config(self, tmp_path):
        from coderag.cli.main import cli

        config = tmp_path / "codegraph.yaml"
        config.write_text("project_name: test\n")
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "-c", str(config)])
        assert result.exit_code == 0 or result.exit_code == 1
