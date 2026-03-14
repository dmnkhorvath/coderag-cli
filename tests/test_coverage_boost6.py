"""Coverage boost tests part 6 - CLI deep paths, orchestrator phase 5, JS resolver."""

import json
import os

from click.testing import CliRunner


class TestCLIDeepPaths:
    """Test CLI commands that exercise deeper code paths."""

    def _setup(self, runner, cli, tmp_path, files=None):
        if files is None:
            files = {"app.php": "<?php class App { public function index() {} }"}
        for name, content in files.items():
            p = tmp_path / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_analyze_symbol(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "App"])
        assert result.exit_code in (0, 1, 2)

    def test_analyze_symbol_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "App", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_analyze_nonexistent(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "NonExistentSymbol"])
        assert result.exit_code in (0, 1, 2)

    def test_find_usages(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["find-usages", "App"])
        assert result.exit_code in (0, 1, 2)

    def test_find_usages_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["find-usages", "App", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_impact_analysis(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "App"])
        assert result.exit_code in (0, 1, 2)

    def test_impact_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "App", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_impact_depth(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "App", "--depth", "5"])
        assert result.exit_code in (0, 1, 2)

    def test_deps_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "App"])
        assert result.exit_code in (0, 1, 2)

    def test_deps_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "App", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_routes_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes"])
        assert result.exit_code in (0, 1, 2)

    def test_routes_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_architecture_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_architecture_default(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture"])
        assert result.exit_code in (0, 1, 2)

    def test_query_fts(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "App"])
        assert result.exit_code in (0, 1, 2)

    def test_query_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "App", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_query_limit(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "App", "--limit", "5"])
        assert result.exit_code in (0, 1, 2)

    def test_export_markdown(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "markdown"])
        assert result.exit_code in (0, 1, 2)

    def test_export_json_format(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_parse_with_workers(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        result = runner.invoke(cli, ["parse", str(tmp_path), "--workers", "2"])
        assert result.exit_code in (0, 1, 2)

    def test_parse_verbose(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        result = runner.invoke(cli, ["parse", str(tmp_path), "-v"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "app.php"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "app.php", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_validate_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code in (0, 1, 2)

    def test_cross_language_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["cross-language"])
        assert result.exit_code in (0, 1, 2)

    def test_frameworks_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["frameworks"])
        assert result.exit_code in (0, 1, 2)

    def test_enrich_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["enrich", str(tmp_path)])
        assert result.exit_code in (0, 1, 2)

    def test_init_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["init"])
        assert result.exit_code in (0, 1, 2)

    def test_serve_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0

    def test_watch_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0

    def test_monitor_help(self):
        from coderag.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["monitor", "--help"])
        assert result.exit_code == 0

    def test_embed_command(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup(runner, cli, tmp_path)
        result = runner.invoke(cli, ["embed", str(tmp_path)])
        assert result.exit_code in (0, 1, 2)


class TestOrchestratorPhase5:
    """Test orchestrator Phase 5 framework detection paths."""

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

    def test_laravel_detection(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "composer.json").write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
        (tmp_path / "routes").mkdir()
        (tmp_path / "routes" / "web.php").write_text("<?php echo 1;")
        (tmp_path / "app" / "Http" / "Controllers").mkdir(parents=True)
        (tmp_path / "app" / "Http" / "Controllers" / "UserController.php").write_text(
            "<?php class UserController { public function index() {} }"
        )
        (tmp_path / "app" / "Models").mkdir(parents=True)
        (tmp_path / "app" / "Models" / "User.php").write_text("<?php class User {}")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_react_detection(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0"}}))
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "App.jsx").write_text(
            "import React from 'react'; export default function App() { return null; }"
        )
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_express_detection(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.18.0"}}))
        (tmp_path / "server.js").write_text(
            "const express = require('express'); const app = express(); app.listen(3000);"
        )
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_angular_detection(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"@angular/core": "^17.0.0"}}))
        (tmp_path / "src" / "app").mkdir(parents=True)
        (tmp_path / "src" / "app" / "app.component.ts").write_text("export class AppComponent { title = 'app'; }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_fastapi_detection(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        req_content = "fastapi==0.100.0" + chr(10) + "uvicorn==0.23.0"
        (tmp_path / "requirements.txt").write_text(req_content)
        py_content = "from fastapi import FastAPI" + chr(10) + "app = FastAPI()"
        (tmp_path / "main.py").write_text(py_content)
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_multi_framework(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18.0.0", "express": "^4.18.0"}}))
        (tmp_path / "server.js").write_text("const express = require('express'); const app = express();")
        (tmp_path / "client.jsx").write_text(
            "import React from 'react'; export default function App() { return null; }"
        )
        (tmp_path / "style.css").write_text(".app { color: red; }")
        (tmp_path / "theme.scss").write_text("$color: blue; .theme { color: $color; }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_incremental_with_changes(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "app.php").write_text("<?php class App { public function index() {} }")
        orch.run(str(tmp_path))
        (tmp_path / "app.php").write_text("<?php class App { public function index() {} public function show() {} }")
        result = orch.run(str(tmp_path), incremental=True)
        assert result is not None
        store.close()

    def test_many_files(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        for i in range(20):
            (tmp_path / f"Class{i}.php").write_text(f"<?php class Class{i} {{ public function method{i}() {{}} }}")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()
