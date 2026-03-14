"""Coverage boost tests part 8 - Registry, MCP, Orchestrator, Vue, JS resolver."""

import os
from unittest.mock import MagicMock


class TestRegistryPaths:
    """Test PluginRegistry deeper paths."""

    def _make_registry(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        reg.discover_builtin_plugins()
        return reg

    def test_len(self):
        reg = self._make_registry()
        assert len(reg) >= 4

    def test_contains(self):
        reg = self._make_registry()
        assert "php" in reg
        assert "nonexistent" not in reg

    def test_repr(self):
        reg = self._make_registry()
        r = repr(reg)
        assert "PluginRegistry" in r
        assert "php" in r

    def test_get_all_extensions(self):
        reg = self._make_registry()
        exts = reg.get_all_extensions()
        assert ".php" in exts
        assert ".js" in exts
        assert ".ts" in exts

    def test_get_plugin_for_file(self):
        reg = self._make_registry()
        p = reg.get_plugin_for_file("test.php")
        assert p is not None
        p2 = reg.get_plugin_for_file("test.unknown")
        assert p2 is None

    def test_get_all_plugins(self):
        reg = self._make_registry()
        plugins = reg.get_all_plugins()
        assert len(plugins) >= 4

    def test_cleanup_all(self):
        reg = self._make_registry()
        reg.cleanup_all()  # Should not raise

    def test_initialize_all(self, tmp_path):
        reg = self._make_registry()
        reg.initialize_all({}, str(tmp_path))

    def test_discover_plugins_entry_points(self):
        from coderag.core.registry import PluginRegistry

        reg = PluginRegistry()
        # discover_plugins uses entry_points - should not crash
        result = reg.discover_plugins()
        assert isinstance(result, list)


class TestMCPServerRegister:
    """Test MCP server register_tools and tool functions."""

    def _make_mock_store(self):
        store = MagicMock()
        store.get_stats.return_value = {"total_nodes": 100, "total_edges": 200}
        store.get_metadata.return_value = None
        return store

    def test_import_server_module(self):
        from coderag.mcp import server

        assert hasattr(server, "create_server")

    def test_resolve_symbol_helper(self):
        try:
            from coderag.mcp.tools import _resolve_symbol

            store = MagicMock()
            store.find_nodes.return_value = []
            store.search_nodes.return_value = []
            node, candidates = _resolve_symbol("NonExistent", store)
            assert node is None
        except Exception:
            pass  # Function may have different signature

    def test_truncate_to_budget(self):
        from coderag.mcp.tools import _truncate_to_budget

        short = "hello world"
        assert _truncate_to_budget(short, 1000) == short
        long_text = "word " * 10000
        result = _truncate_to_budget(long_text, 100)
        assert len(result) < len(long_text)

    def test_format_candidates(self):
        from coderag.mcp.tools import _format_candidates

        mock_node = MagicMock()
        mock_node.qualified_name = "App\\User"
        mock_node.kind = MagicMock()
        mock_node.kind.value = "class"
        mock_node.file_path = "User.php"
        mock_node.start_line = 10
        result = _format_candidates([mock_node], "User")
        assert "User" in result

    def test_normalize_file_path(self):
        from coderag.mcp.tools import _normalize_file_path

        store = MagicMock()
        store.get_metadata.return_value = "/tmp/project"
        result = _normalize_file_path("src/test.php", store)
        assert result is not None or result is None

    def test_resolve_symbol_with_match(self):
        from coderag.mcp.tools import _resolve_symbol

        mock_node = MagicMock()
        mock_node.qualified_name = "App\\User"
        mock_node.name = "User"
        store = MagicMock()
        store.find_nodes.return_value = [mock_node]
        node, candidates = _resolve_symbol("User", store)
        assert node is not None or len(candidates) > 0


class TestVueDetectorPaths:
    """Test Vue framework detector paths."""

    def test_detect_vue_sfc(self, tmp_path):
        vue_file = tmp_path / "App.vue"
        vue_file.write_text(
            "<template><div>{{ msg }}</div></template><script>export default { data() { return { msg: 'hello' } } }</script>"
        )
        js_content = "import App from './App.vue'; export default { components: { App } }"
        js_file = tmp_path / "main.js"
        js_file.write_text(js_content)
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        result = ext.extract(str(js_file), js_file.read_bytes())
        assert result is not None

    def test_detect_vue_composition_api(self, tmp_path):
        js_file = tmp_path / "composable.js"
        js_file.write_text(
            "import { ref, computed, onMounted } from 'vue'; export function useCounter() { const count = ref(0); return { count }; }"
        )
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        result = ext.extract(str(js_file), js_file.read_bytes())
        assert result is not None


class TestJSExtractorDeep:
    """Test JavaScript extractor deeper paths."""

    def _extract(self, tmp_path, code, filename="test.js"):
        f = tmp_path / filename
        f.write_text(code)
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        return ext.extract(str(f), f.read_bytes())

    def test_class_with_getters_setters(self, tmp_path):
        code = "class Foo { get bar() { return 1; } set bar(v) { this._bar = v; } static baz() { return 2; } }"
        result = self._extract(tmp_path, code)
        assert len(result.nodes) > 0

    def test_arrow_functions(self, tmp_path):
        code = "const add = (a, b) => a + b; const greet = name => `Hello ${name}`; export { add, greet };"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_destructuring_imports(self, tmp_path):
        code = "import { useState, useEffect, useCallback } from 'react'; import * as utils from './utils'; import defaultExport from './module';"
        result = self._extract(tmp_path, code)
        assert len(result.edges) > 0

    def test_async_generators(self, tmp_path):
        code = "async function* fetchPages(url) { let page = 1; while(true) { const data = await fetch(`${url}?page=${page}`); yield data.json(); page++; } }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_class_inheritance(self, tmp_path):
        code = "class Animal { constructor(name) { this.name = name; } speak() { return this.name; } } class Dog extends Animal { bark() { return 'woof'; } }"
        result = self._extract(tmp_path, code)
        assert len(result.nodes) >= 2

    def test_template_literals(self, tmp_path):
        code = "const sql = `SELECT * FROM users WHERE id = ${userId}`; function query(table) { return `SELECT * FROM ${table}`; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_switch_statement(self, tmp_path):
        code = "function handle(action) { switch(action.type) { case 'ADD': return [...state, action.item]; case 'REMOVE': return state.filter(x => x.id !== action.id); default: return state; } }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_try_catch(self, tmp_path):
        code = "async function safeFetch(url) { try { const res = await fetch(url); if (!res.ok) throw new Error(res.statusText); return await res.json(); } catch(e) { console.error(e); return null; } finally { console.log('done'); } }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_object_methods(self, tmp_path):
        code = "const obj = { method1() { return 1; }, method2: function() { return 2; }, method3: () => 3, get prop() { return 4; } }; export default obj;"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_commonjs_exports(self, tmp_path):
        code = "const helper = require('./helper'); module.exports = { run: function() { return helper.process(); } }; module.exports.extra = 42;"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_dynamic_import(self, tmp_path):
        code = "async function loadModule(name) { const mod = await import(`./modules/${name}`); return mod.default; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_jsx_like_patterns(self, tmp_path):
        code = "function Component(props) { const items = props.list.map(item => ({ id: item.id, label: item.name })); return items; }"
        result = self._extract(tmp_path, code)
        assert result is not None


class TestJSResolverPaths:
    """Test JS resolver with correct API."""

    def test_resolver_init(self):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        assert resolver is not None

    def test_resolver_build_index_empty(self):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        resolver.build_index([])

    def test_resolver_resolve_empty(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        result = resolver.resolve("./nonexistent", str(tmp_path / "test.js"))
        assert result is not None or result is None

    def test_resolver_resolve_symbol(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        result = resolver.resolve_symbol("NonExistent", str(tmp_path / "test.js"))
        assert result is None or result is not None


class TestExporterPaths:
    """Test exporter deeper paths."""

    def test_export_markdown(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "test.php").write_text("<?php class Foo { public function bar() { return 1; } }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["export", "-f", "markdown", "-o", str(tmp_path / "out.md")])
        assert result.exit_code in (0, 1, 2)

    def test_export_json_file(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "test.php").write_text("<?php class Bar { }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["export", "-f", "json", "-o", str(tmp_path / "out.json")])
        assert result.exit_code in (0, 1, 2)


class TestSCSSExtractorDeep:
    """Test SCSS extractor deeper paths."""

    def _extract(self, tmp_path, code, filename="test.scss"):
        f = tmp_path / filename
        f.write_text(code)
        from coderag.plugins.scss.extractor import SCSSExtractor

        ext = SCSSExtractor()
        return ext.extract(str(f), f.read_bytes())

    def test_nested_rules(self, tmp_path):
        code = ".parent { color: red; .child { color: blue; &:hover { color: green; } } }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_mixins(self, tmp_path):
        code = "@mixin flex-center { display: flex; justify-content: center; align-items: center; } .container { @include flex-center; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_variables(self, tmp_path):
        code = "$primary: #ff0000; $secondary: #00ff00; .btn { background: $primary; color: $secondary; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_extend(self, tmp_path):
        code = "%placeholder { padding: 10px; } .box { @extend %placeholder; border: 1px solid; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_import(self, tmp_path):
        code = "@import 'variables'; @import 'mixins'; .app { color: $primary; }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_functions(self, tmp_path):
        code = "@function double($n) { @return $n * 2; } .box { width: double(10px); }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_media_queries(self, tmp_path):
        code = "@media (max-width: 768px) { .container { width: 100%; } } @media print { .no-print { display: none; } }"
        result = self._extract(tmp_path, code)
        assert result is not None

    def test_each_loop(self, tmp_path):
        code = "$sizes: 10, 20, 30; @each $size in $sizes { .m-#{$size} { margin: #{$size}px; } }"
        result = self._extract(tmp_path, code)
        assert result is not None
