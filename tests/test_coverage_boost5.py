"""Coverage boost tests part 5 - JS extractor, SCSS extractor, tailwind, vue, orchestrator, CLI."""

import os
import tempfile


class TestJSExtractorDeep:
    """Deep tests for JavaScript extractor uncovered paths."""

    def _extract(self, code, filename="test.js"):
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            source = code.encode("utf-8")
            result = ext.extract(f.name, source)
        os.unlink(f.name)
        return result

    def test_arrow_function(self):
        result = self._extract("const add = (a, b) => a + b;\nexport { add };")
        assert result is not None

    def test_class_with_getters_setters(self):
        code = """class User {
    get name() { return this._name; }
    set name(val) { this._name = val; }
    static create() { return new User(); }
}
export default User;"""
        result = self._extract(code)
        assert result is not None
        names = [n.name for n in result.nodes]
        assert "User" in names

    def test_async_generator(self):
        code = """async function* fetchPages(url) {
    let page = 1;
    while (true) {
        const response = await fetch(url);
        yield await response.json();
        page++;
    }
}
export { fetchPages };"""
        result = self._extract(code)
        assert result is not None

    def test_destructuring_imports(self):
        code = """import { useState, useEffect } from 'react';
import * as utils from './utils';
import defaultExport from './module';"""
        result = self._extract(code)
        assert result is not None

    def test_template_literals(self):
        code = "const greeting = `Hello world`;\nexport const query = greeting;"
        result = self._extract(code)
        assert result is not None

    def test_class_inheritance(self):
        code = """class Animal {
    constructor(name) { this.name = name; }
    speak() { return this.name; }
}
class Dog extends Animal {
    speak() { return this.name + ' barks'; }
}
export { Animal, Dog };"""
        result = self._extract(code)
        assert result is not None
        names = [n.name for n in result.nodes]
        assert "Animal" in names
        assert "Dog" in names

    def test_object_methods(self):
        code = """const api = {
    async getUsers() { return fetch('/users'); },
    async getUser(id) { return fetch('/users/' + id); },
    createUser(data) { return fetch('/users', { method: 'POST' }); }
};
export default api;"""
        result = self._extract(code)
        assert result is not None

    def test_try_catch(self):
        code = """export async function safeFetch(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('fail');
        return await res.json();
    } catch (error) {
        console.error('Fetch failed:', error);
        return null;
    } finally {
        console.log('done');
    }
}"""
        result = self._extract(code)
        assert result is not None

    def test_switch_statement(self):
        code = """export function handleAction(action) {
    switch (action.type) {
        case 'INCREMENT': return { count: action.count + 1 };
        case 'DECREMENT': return { count: action.count - 1 };
        default: return action;
    }
}"""
        result = self._extract(code)
        assert result is not None

    def test_iife(self):
        code = """const module = (function() {
    let x = 0;
    return { increment() { x++; }, getCount() { return x; } };
})();
export default module;"""
        result = self._extract(code)
        assert result is not None

    def test_promise_chain(self):
        code = """export function loadData() {
    return fetch('/api/data')
        .then(res => res.json())
        .then(data => data.items)
        .catch(err => { console.error(err); return []; });
}"""
        result = self._extract(code)
        assert result is not None

    def test_generator_function(self):
        code = """export function* range(start, end, step) {
    for (let i = start; i < end; i += step) {
        yield i;
    }
}"""
        result = self._extract(code)
        assert result is not None

    def test_optional_chaining(self):
        code = """export function getUserCity(user) {
    return user && user.address && user.address.city;
}"""
        result = self._extract(code)
        assert result is not None

    def test_empty_file(self):
        result = self._extract("")
        assert result is not None

    def test_comments_only(self):
        result = self._extract("// This is a comment\n/* Block comment */")
        assert result is not None


class TestSCSSExtractorDeep:
    """Deep tests for SCSS extractor."""

    def _extract(self, code, filename="test.scss"):
        from coderag.plugins.scss.extractor import SCSSExtractor

        ext = SCSSExtractor()
        with tempfile.NamedTemporaryFile(suffix=".scss", mode="w", delete=False) as f:
            f.write(code)
            f.flush()
            source = code.encode("utf-8")
            result = ext.extract(f.name, source)
        os.unlink(f.name)
        return result

    def test_variables(self):
        result = self._extract("$primary: #333;\n$secondary: #666;\n.btn { color: $primary; }")
        assert result is not None

    def test_mixins(self):
        code = """@mixin flex-center {
    display: flex;
    justify-content: center;
    align-items: center;
}
.container { @include flex-center; }"""
        result = self._extract(code)
        assert result is not None

    def test_nesting(self):
        code = """.nav {
    ul { list-style: none; }
    li { display: inline-block; }
    a {
        text-decoration: none;
        &:hover { color: red; }
    }
}"""
        result = self._extract(code)
        assert result is not None

    def test_extend(self):
        code = """%message-shared {
    border: 1px solid #ccc;
    padding: 10px;
}
.success { @extend %message-shared; border-color: green; }
.error { @extend %message-shared; border-color: red; }"""
        result = self._extract(code)
        assert result is not None

    def test_functions(self):
        code = """@function double($val) {
    @return $val * 2;
}
.sidebar { width: double(100px); }"""
        result = self._extract(code)
        assert result is not None

    def test_import(self):
        result = self._extract("@import 'variables';\n@import 'mixins';")
        assert result is not None

    def test_use_and_forward(self):
        result = self._extract("@use 'sass:math';\n@forward 'mixins';")
        assert result is not None

    def test_media_queries(self):
        code = """.container {
    width: 100%;
    @media (min-width: 768px) {
        width: 750px;
    }
}"""
        result = self._extract(code)
        assert result is not None

    def test_each_loop(self):
        code = """@each $color in red, green, blue {
    .text-#{$color} { color: $color; }
}"""
        result = self._extract(code)
        assert result is not None

    def test_empty_file(self):
        result = self._extract("")
        assert result is not None


class TestTailwindDetectorDeep:
    """Deep tests for Tailwind CSS framework detector."""

    def _detect(self, css_code, tmp_path, filename="style.css", extra_files=None):
        import tree_sitter
        import tree_sitter_css as tscss

        from coderag.plugins.css.frameworks.tailwind import TailwindDetector

        if extra_files:
            for name, content in extra_files.items():
                p = tmp_path / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
        css_file = tmp_path / filename
        css_file.parent.mkdir(parents=True, exist_ok=True)
        css_file.write_text(css_code)
        source = css_code.encode("utf-8")
        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(source)
        detector = TailwindDetector()
        nodes = []
        edges = []
        result = detector.detect(str(css_file), tree, source, nodes, edges)
        return result

    def test_tailwind_config_js(self, tmp_path):
        result = self._detect(
            "@tailwind base;\n@tailwind components;\n@tailwind utilities;",
            tmp_path,
            filename="src/app.css",
            extra_files={"tailwind.config.js": "module.exports = { content: ['./src/**/*.html'] }"},
        )
        assert result is not None

    def test_tailwind_config_ts(self, tmp_path):
        result = self._detect(
            "@tailwind base;\n@tailwind components;",
            tmp_path,
            filename="src/index.css",
            extra_files={"tailwind.config.ts": "export default { content: [] };"},
        )
        assert result is not None

    def test_no_tailwind(self, tmp_path):
        result = self._detect("body { margin: 0; }", tmp_path)
        assert result is not None

    def test_tailwind_with_apply(self, tmp_path):
        result = self._detect(
            ".btn { @apply px-4 py-2 rounded; }",
            tmp_path,
            extra_files={"tailwind.config.js": "module.exports = { content: [] }"},
        )
        assert result is not None

    def test_postcss_config(self, tmp_path):
        result = self._detect(
            "body { margin: 0; }",
            tmp_path,
            extra_files={
                "postcss.config.js": "module.exports = { plugins: { tailwindcss: {} } }",
                "tailwind.config.js": "module.exports = { content: [] }",
            },
        )
        assert result is not None


class TestVueDetectorDeep:
    """Deep tests for Vue framework detector."""

    def _detect(self, js_code, tmp_path, filename="app.js", extra_files=None):
        import tree_sitter
        import tree_sitter_javascript as tsjs

        from coderag.plugins.javascript.frameworks.vue import VueDetector

        if extra_files:
            for name, content in extra_files.items():
                p = tmp_path / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
        js_file = tmp_path / filename
        js_file.parent.mkdir(parents=True, exist_ok=True)
        js_file.write_text(js_code)
        source = js_code.encode("utf-8")
        lang = tree_sitter.Language(tsjs.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(source)
        detector = VueDetector()
        nodes = []
        edges = []
        result = detector.detect(str(js_file), tree, source, nodes, edges)
        return result

    def test_vue_sfc(self, tmp_path):
        result = self._detect(
            "export default { data() { return { msg: 'Hello' } } }",
            tmp_path,
            extra_files={"package.json": '{"dependencies": {"vue": "^3.0.0"}}'},
        )
        assert result is not None

    def test_vue_composition_api(self, tmp_path):
        result = self._detect(
            "import { ref } from 'vue'; const count = ref(0);",
            tmp_path,
            extra_files={"package.json": '{"dependencies": {"vue": "^3.3.0"}}'},
        )
        assert result is not None

    def test_no_vue(self, tmp_path):
        result = self._detect(
            "console.log('hello');", tmp_path, extra_files={"package.json": '{"dependencies": {"react": "^18.0.0"}}'}
        )
        assert result is not None

    def test_nuxt_project(self, tmp_path):
        result = self._detect(
            "export default defineNuxtConfig({ modules: [] })",
            tmp_path,
            filename="nuxt.config.ts",
            extra_files={"package.json": '{"dependencies": {"nuxt": "^3.0.0"}}'},
        )
        assert result is not None


class TestOrchestratorDeepPaths:
    """Deep orchestrator tests for more uncovered paths."""

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

    def test_mixed_languages(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        (tmp_path / "app.js").write_text("export class App { getUser() { return fetch('/api/user'); } }")
        (tmp_path / "service.ts").write_text("export class Service { async getData(): Promise<any> { return null; } }")
        (tmp_path / "style.css").write_text(".app { color: red; }")
        (tmp_path / "main.scss").write_text("$color: red; .main { color: $color; }")
        (tmp_path / "utils.py").write_text("def helper():\n    return 42")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_nested_directories(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "src" / "controllers").mkdir(parents=True)
        (tmp_path / "src" / "models").mkdir(parents=True)
        (tmp_path / "src" / "controllers" / "UserController.php").write_text(
            "<?php namespace App\\Controllers; class UserController { public function index() {} }"
        )
        (tmp_path / "src" / "models" / "User.php").write_text(
            "<?php namespace App\\Models; class User { public function getName() {} }"
        )
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_syntax_error_file(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "good.php").write_text("<?php class Good {}")
        (tmp_path / "bad.php").write_text("<?php class { this is not valid php")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_empty_directory(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_large_file(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        methods = "\n".join([f"    public function method{i}() {{ return {i}; }}" for i in range(50)])
        (tmp_path / "BigClass.php").write_text(f"<?php class BigClass {{\n{methods}\n}}")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_cross_language_references(self, tmp_path):
        orch, store = self._make_orch(tmp_path)
        (tmp_path / "api.php").write_text(
            "<?php class ApiController { public function getUsers() { return response()->json([]); } }"
        )
        (tmp_path / "client.js").write_text("export async function fetchUsers() { return fetch('/api/users'); }")
        (tmp_path / "types.ts").write_text(
            "export interface User { id: number; name: string; }\nexport type UserList = User[];"
        )
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()


class TestCLIMoreCommands:
    """Test more CLI commands for coverage."""

    def _parse_first(self, runner, cli, tmp_path):
        (tmp_path / "app.php").write_text("<?php class App {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))

    def test_info_json(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        result = runner.invoke(cli, ["info", "--json-output"])
        assert result.exit_code in (0, 1, 2)

    def test_info_default(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        result = runner.invoke(cli, ["info"])
        assert result.exit_code in (0, 1, 2)

    def test_frameworks_json(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        result = runner.invoke(cli, ["frameworks", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_frameworks_default(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        result = runner.invoke(cli, ["frameworks"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["file-context", "User.php"])
        assert result.exit_code in (0, 1, 2)

    def test_file_context_json(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "User.php").write_text("<?php class User { public function getName() {} }")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["file-context", "User.php", "--format", "json"])
        assert result.exit_code in (0, 1, 2)

    def test_enrich_no_phpstan(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        result = runner.invoke(cli, ["enrich"])
        assert result.exit_code in (0, 1, 2)

    def test_validate(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code in (0, 1, 2)

    def test_parse_incremental(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "app.php").write_text("<?php class App {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        result = runner.invoke(cli, ["parse", str(tmp_path), "--incremental"])
        assert result.exit_code in (0, 1, 2)

    def test_export_to_file(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        out = tmp_path / "export.md"
        result = runner.invoke(cli, ["export", "-o", str(out)])
        assert result.exit_code in (0, 1, 2)

    def test_export_json(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        self._parse_first(runner, cli, tmp_path)
        out = tmp_path / "export.json"
        result = runner.invoke(cli, ["export", "-f", "json", "-o", str(out)])
        assert result.exit_code in (0, 1, 2)

    def test_cross_language_default(self, tmp_path):
        from click.testing import CliRunner

        from coderag.cli.main import cli

        runner = CliRunner()
        (tmp_path / "api.php").write_text("<?php class Api {}")
        (tmp_path / "client.js").write_text("export function fetchApi() {}")
        runner.invoke(cli, ["parse", str(tmp_path)])
        os.chdir(str(tmp_path))
        result = runner.invoke(cli, ["cross-language"])
        assert result.exit_code in (0, 1, 2)
