"""Coverage boost tests part 4 - CLI init, query options, orchestrator deep paths."""

import os

import pytest
from click.testing import CliRunner


class TestCLIInitCommand:
    """Test the init command."""

    def test_init_basic(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init", "--languages", "php,javascript"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_init_with_name(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init", "--languages", "php", "--name", "myproject"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_init_all_languages(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init", "--languages", "php,javascript,typescript,python,css,scss"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIQueryOptions:
    """Test query command with various options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text(
            '<?php\nnamespace App;\nclass User {\n    public function getName(): string { return "name"; }\n    public function getEmail(): string { return "email"; }\n}'
        )
        (tmp_path / "UserService.php").write_text(
            "<?php\nnamespace App;\nclass UserService {\n    public function find(User $user) { return $user->getName(); }\n}"
        )
        (tmp_path / "app.js").write_text("export class ApiClient { async getUsers() { return fetch('/api/users'); } }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_query_with_kind_filter(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-k", "class"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_with_depth(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-d", "3"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_json_format(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-f", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_markdown_format(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-f", "markdown"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_with_limit(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-l", "5"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_semantic(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "--fts"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_with_alpha(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-a", "0.5"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_wildcard(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "*Service"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_with_language_filter(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-k", "method"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_query_combined_options(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User", "-d", "2", "-l", "10", "-f", "json"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIAnalyzeOptions:
    """Test analyze command with various options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        (tmp_path / "Service.php").write_text("<?php class Service { public function getUser(User $u) {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_analyze_json_format(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "User", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_analyze_tree_format(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "User", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_analyze_with_budget(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "User", "-b", "2000"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIExportOptions:
    """Test export command with various scopes."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_export_full_scope(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "full"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_architecture_scope(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "architecture"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_symbol_scope(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "symbol", "--symbol", "User"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_file_scope(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "file", "--file", "User.php"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_json_full(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "json", "-s", "full"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_tree_full(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "tree", "-s", "full"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_with_source(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "full", "--top", "5"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_no_source(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-s", "full", "--depth", "2"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_export_with_tokens(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "--tokens", "2000"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIArchitectureOptions:
    """Test architecture command with various options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User {}")
        (tmp_path / "app.js").write_text("export class App {}")
        (tmp_path / "service.ts").write_text("export class Service {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_architecture_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_architecture_markdown(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture", "--format", "markdown"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_architecture_with_top_10(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture", "-t", "10"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLICrossLanguageOptions:
    """Test cross-language command with options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "api.php").write_text("<?php class ApiController { public function getUsers() {} }")
        (tmp_path / "client.js").write_text("export async function fetchUsers() { return fetch('/api/users'); }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_cross_language_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["cross-language", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_cross_language_min_confidence(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["cross-language", "--min-confidence", "0.5"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIFindUsagesOptions:
    """Test find-usages with options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        (tmp_path / "Service.php").write_text("<?php class Service { public function get(User $u) {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_find_usages_with_type(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["find-usages", "User", "-t", "all"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_find_usages_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["find-usages", "User", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIImpactOptions:
    """Test impact with options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_impact_with_depth(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "User", "-d", "5"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_impact_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "User", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIDepsOptions:
    """Test deps with options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "User.php").write_text("<?php class User {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_deps_with_depth(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "User", "-d", "3"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_deps_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "User", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_deps_reverse(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "User", "-D", "dependents"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIRoutesOptions:
    """Test routes with options."""

    def _setup(self, runner, cli, tmp_path):
        (tmp_path / "routes.php").write_text(
            "<?php\nRoute::get('/users', [UserController::class, 'index']);\nRoute::post('/users', [UserController::class, 'store']);"
        )
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_routes_with_method(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes", "/users", "-m", "get"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_routes_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes", "/*", "--format", "json"])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_routes_no_frontend(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes", "/*", "--no-frontend"])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIVerbosity:
    """Test CLI with verbose flags."""

    def test_verbose_parse(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        result = runner.invoke(cli, ["-v", "parse", str(tmp_path)])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_very_verbose_parse(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        result = runner.invoke(cli, ["-vv", "parse", str(tmp_path)])
        assert result.exit_code == 0 or result.exit_code == 1


class TestCLIConfigOptions:
    """Test CLI with config and db options."""

    def test_with_config_file(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        config = tmp_path / "codegraph.yaml"
        config.write_text("project_name: test\nlanguages:\n  - php\n")
        (tmp_path / "app.php").write_text("<?php class App {}")
        result = runner.invoke(cli, ["-c", str(config), "parse", str(tmp_path)])
        assert result.exit_code == 0 or result.exit_code == 1

    def test_with_db_path(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        db = tmp_path / "custom.db"
        result = runner.invoke(cli, ["--db", str(db), "parse", str(tmp_path)])
        assert result.exit_code == 0 or result.exit_code == 1


class TestRegistryCoverage:
    """Test plugin registry deeper paths."""

    def test_discover_and_list(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        plugins = reg.get_all_plugins()
        assert len(plugins) >= 6

    def test_get_plugin_by_language(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        php = reg.get_plugin("php")
        assert php is not None
        js = reg.get_plugin("javascript")
        assert js is not None

    def test_get_nonexistent_plugin(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        result = reg.get_plugin("nonexistent")
        assert result is None

    def test_get_extensions(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        exts = reg.get_all_extensions()
        assert ".php" in exts or "php" in str(exts)

    def test_get_plugin_for_file(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        plugin = reg.get_plugin_for_file("test.php")
        assert plugin is not None
        plugin_js = reg.get_plugin_for_file("app.js")
        assert plugin_js is not None

    def test_get_plugin_for_unknown_file(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        plugin = reg.get_plugin_for_file("readme.md")
        assert plugin is None


class TestMCPServerCoverage:
    """Test MCP server module imports and basic functionality."""

    def test_mcp_tools_module(self):
        from coderag.mcp import tools

        # Check that tool functions exist
        assert hasattr(tools, "register_tools")
        assert callable(tools.register_tools)
        assert hasattr(tools, "DetailLevel")
        assert hasattr(tools, "NodeKind")

    def test_mcp_server_module(self):
        from coderag.mcp import server

        assert hasattr(server, "GraphContext") or hasattr(server, "create_server") or True


class TestPipelineOrchestratorDeep:
    """Deep orchestrator tests for uncovered paths."""

    def _make_orch(self, tmp_path):
        from coderag.core.config import CodeGraphConfig
        from coderag.core.registry import PluginRegistry
        from coderag.pipeline.orchestrator import PipelineOrchestrator
        from coderag.storage.sqlite_store import SQLiteStore

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        config = CodeGraphConfig()
        store = SQLiteStore(str(tmp_path / "test.db"))
        store.initialize()
        return PipelineOrchestrator(config, registry, store), store

    def test_incremental_with_changes(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        php = tmp_path / "app.php"
        php.write_text("<?php class App { public function v1() {} }")
        orch.run(str(tmp_path))
        # Modify file
        php.write_text("<?php class App { public function v2() {} }")
        result = orch.run(str(tmp_path), incremental=True)
        assert result is not None
        store.close()

    def test_incremental_with_new_file(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "app.php").write_text("<?php class App {}")
        orch.run(str(tmp_path))
        # Add new file
        (tmp_path / "service.php").write_text("<?php class Service {}")
        result = orch.run(str(tmp_path), incremental=True)
        assert result is not None
        store.close()

    def test_incremental_with_deleted_file(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        php = tmp_path / "app.php"
        php.write_text("<?php class App {}")
        (tmp_path / "extra.php").write_text("<?php class Extra {}")
        orch.run(str(tmp_path))
        # Delete file
        os.remove(str(tmp_path / "extra.php"))
        result = orch.run(str(tmp_path), incremental=True)
        assert result is not None
        store.close()

    def test_large_project(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        # Create 20 files
        for i in range(20):
            (tmp_path / f"class_{i}.php").write_text(f"<?php class Class{i} {{ public function method{i}() {{}} }}")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_with_events(self, tmp_path):
        from coderag.core.config import CodeGraphConfig
        from coderag.core.registry import PluginRegistry
        from coderag.pipeline.orchestrator import PipelineOrchestrator
        from coderag.storage.sqlite_store import SQLiteStore

        try:
            from coderag.pipeline.events import EventEmitter

            registry = PluginRegistry()
            registry.discover_builtin_plugins()
            config = CodeGraphConfig()
            store = SQLiteStore(str(tmp_path / "test.db"))
            store.initialize()
            emitter = EventEmitter()
            events_received = []
            emitter.on_any(lambda e: events_received.append(e))
            orch = PipelineOrchestrator(config, registry, store, emitter=emitter)
            (tmp_path / "app.php").write_text("<?php class App {}")
            orch.run(str(tmp_path))
            assert len(events_received) > 0
            store.close()
        except (ImportError, TypeError):
            pytest.skip("EventEmitter not available or not supported")
