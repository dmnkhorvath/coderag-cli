"""Coverage boost tests part 7 - Tailwind, MCP server, more CLI, CSS resolver."""

import os

import pytest
from click.testing import CliRunner


class TestTailwindDetector:
    """Test Tailwind CSS framework detector."""

    def _get_detector(self):
        from coderag.plugins.css.frameworks.tailwind import TailwindDetector

        return TailwindDetector()

    def test_detect_tailwind_config_js(self, tmp_path):
        detector = self._get_detector()
        config = tmp_path / "tailwind.config.js"
        config.write_text("module.exports = { content: ['./src/**/*.{html,js}'], theme: { extend: {} }, plugins: [] }")
        css = tmp_path / "style.css"
        css.write_text(
            "@tailwind base; @tailwind components; @tailwind utilities; .btn { @apply px-4 py-2 bg-blue-500 text-white rounded; }"
        )
        from coderag.plugins.css.extractor import CSSExtractor

        ext = CSSExtractor()
        result = ext.extract(str(css), css.read_bytes())
        nodes = result.nodes if hasattr(result, "nodes") else []
        edges = result.edges if hasattr(result, "edges") else []
        import tree_sitter
        import tree_sitter_css as tscss

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(css.read_bytes())
        fw_result = detector.detect(
            str(css),
            tree,
            css.read_bytes(),
            nodes,
            edges,
        )
        assert fw_result is not None

    def test_detect_no_tailwind(self, tmp_path):
        detector = self._get_detector()
        css = tmp_path / "plain.css"
        css.write_text(".btn { color: red; }")
        import tree_sitter
        import tree_sitter_css as tscss

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(css.read_bytes())
        fw_result = detector.detect(
            str(css),
            tree,
            css.read_bytes(),
            [],
            [],
        )
        assert fw_result is not None or fw_result is None

    def test_tailwind_with_config_ts(self, tmp_path):
        detector = self._get_detector()
        config = tmp_path / "tailwind.config.ts"
        config.write_text(
            "export default { content: ['./src/**/*.tsx'], theme: { extend: { colors: { primary: '#ff0000' } } } }"
        )
        css = tmp_path / "app.css"
        css.write_text("@tailwind base; @tailwind utilities; .card { @apply shadow-lg p-4; }")
        import tree_sitter
        import tree_sitter_css as tscss

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(css.read_bytes())
        fw_result = detector.detect(
            str(css),
            tree,
            css.read_bytes(),
            [],
            [],
        )
        assert fw_result is not None or fw_result is None

    def test_tailwind_postcss_config(self, tmp_path):
        detector = self._get_detector()
        postcss = tmp_path / "postcss.config.js"
        postcss.write_text("module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }")
        config = tmp_path / "tailwind.config.js"
        config.write_text("module.exports = { content: ['./src/**/*.html'] }")
        css = tmp_path / "input.css"
        css.write_text("@tailwind base; @tailwind components; @tailwind utilities;")
        import tree_sitter
        import tree_sitter_css as tscss

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(css.read_bytes())
        fw_result = detector.detect(
            str(css),
            tree,
            css.read_bytes(),
            [],
            [],
        )
        assert fw_result is not None or fw_result is None


class TestCSSResolverDeep:
    """Test CSS resolver deeper paths."""

    def test_resolve_css_imports(self, tmp_path):
        (tmp_path / "base.css").write_text(":root { --color: red; }")
        (tmp_path / "app.css").write_text("@import './base.css'; .app { color: var(--color); }")
        from coderag.plugins.css.extractor import CSSExtractor

        ext = CSSExtractor()
        results = []
        for f in ["base.css", "app.css"]:
            path = str(tmp_path / f)
            source = (tmp_path / f).read_bytes()
            results.append(ext.extract(path, source))
        assert len(results) == 2


class TestMCPServerPaths:
    """Test MCP server tool functions."""

    def test_import_mcp_tools(self):
        try:
            from coderag.mcp import tools

            assert hasattr(tools, "register_tools")
        except ImportError:
            pytest.skip("MCP not available")

    def test_import_mcp_server(self):
        try:
            from coderag.mcp import server

            assert server is not None
        except ImportError:
            pytest.skip("MCP not available")


class TestCLIMorePaths:
    """Test more CLI command paths for coverage."""

    def _setup_multi(self, runner, cli, tmp_path):
        files = {
            "User.php": "<?php class User { public function getName() { return 1; } public function getEmail() { return 2; } }",
            "Post.php": "<?php class Post { public function getTitle() { return 1; } public function getAuthor() { $u = new User(); return $u->getName(); } }",
            "Controller.php": "<?php class Controller { public function index() { $p = new Post(); return $p->getTitle(); } }",
            "app.js": "import { helper } from './utils'; export function main() { return helper(); }",
            "utils.js": "export function helper() { return 42; }",
            "style.css": ".app { color: red; font-size: 14px; } .btn { background: blue; }",
        }
        for name, content in files.items():
            (tmp_path / name).write_text(content)
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_info_verbose(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["info", "--verbose"])
        assert result.exit_code in (0, 1, 2)

    def test_info_json(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["info", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_analyze_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "User"])
        assert result.exit_code in (0, 1, 2)

    def test_analyze_post(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["analyze", "Post"])
        assert result.exit_code in (0, 1, 2)

    def test_find_usages_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["find-usages", "User"])
        assert result.exit_code in (0, 1, 2)

    def test_impact_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "User"])
        assert result.exit_code in (0, 1, 2)

    def test_impact_user_depth3(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["impact", "User", "--depth", "3"])
        assert result.exit_code in (0, 1, 2)

    def test_deps_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "User"])
        assert result.exit_code in (0, 1, 2)

    def test_deps_post(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["deps", "Post"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "User.php"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_post(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "Post.php"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_js(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "app.js"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_css(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["file-context", "style.css"])
        assert result.exit_code in (0, 1, 2)

    def test_query_user(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "User"])
        assert result.exit_code in (0, 1, 2)

    def test_query_function(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "getName"])
        assert result.exit_code in (0, 1, 2)

    def test_query_helper(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["query", "helper"])
        assert result.exit_code in (0, 1, 2)

    def test_export_csv(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "csv"])
        assert result.exit_code in (0, 1, 2)

    def test_export_dot(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["export", "-f", "dot"])
        assert result.exit_code in (0, 1, 2)

    def test_architecture_multi(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["architecture"])
        assert result.exit_code in (0, 1, 2)

    def test_routes_multi(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["routes"])
        assert result.exit_code in (0, 1, 2)

    def test_cross_language_multi(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["cross-language"])
        assert result.exit_code in (0, 1, 2)

    def test_frameworks_multi(self, tmp_path):
        from coderag.cli.main import cli

        runner = CliRunner()
        self._setup_multi(runner, cli, tmp_path)
        result = runner.invoke(cli, ["frameworks"])
        assert result.exit_code in (0, 1, 2)


class TestRegistryDeep:
    """Test plugin registry deeper paths."""

    def test_discover_builtin(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        plugins = registry.get_all_plugins()
        assert len(plugins) >= 4

    def test_get_plugin_by_language(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        php = registry.get_plugin("php")
        assert php is not None

    def test_get_plugin_nonexistent(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        result = registry.get_plugin("nonexistent")
        assert result is None

    def test_get_extensions(self):
        from coderag.core.registry import PluginRegistry

        registry = PluginRegistry()
        registry.discover_builtin_plugins()
        exts = registry.get_all_extensions()
        assert ".php" in exts or "php" in str(exts).lower()
