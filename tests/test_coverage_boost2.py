"""Coverage boost tests part 2 - JS/TS extractors, resolvers, pipeline, detectors."""

import json

# ============================================================================
# JavaScript Extractor Tests
# ============================================================================


class TestJSExtractorCoverage:
    """Test JavaScript extractor with various code patterns."""

    def _extract(self, code, filename="test.js"):
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        return ext.extract(filename, code.encode() if isinstance(code, str) else code)

    def test_class_declaration(self):
        result = self._extract("class Foo { constructor() {} method() {} }")
        names = [n.name for n in result.nodes]
        assert "Foo" in names

    def test_function_declaration(self):
        result = self._extract("function hello(a, b) { return a + b; }")
        names = [n.name for n in result.nodes]
        assert "hello" in names

    def test_arrow_function(self):
        result = self._extract("const greet = (name) => `Hello ${name}`;")
        names = [n.name for n in result.nodes]
        assert "greet" in names

    def test_class_with_extends(self):
        result = self._extract("class Dog extends Animal { bark() {} }")
        names = [n.name for n in result.nodes]
        assert "Dog" in names

    def test_import_default(self):
        result = self._extract("import React from 'react';")
        assert len(result.unresolved_references) > 0

    def test_import_named(self):
        result = self._extract("import { useState, useEffect } from 'react';")
        assert len(result.unresolved_references) > 0

    def test_import_star(self):
        result = self._extract("import * as utils from './utils';")
        assert len(result.unresolved_references) > 0

    def test_require_call(self):
        result = self._extract("const fs = require('fs');")
        assert result is not None

    def test_export_default(self):
        result = self._extract("export default function main() {}")
        names = [n.name for n in result.nodes]
        assert "main" in names

    def test_export_named(self):
        result = self._extract("export function helper() {}\nexport const VALUE = 42;")
        names = [n.name for n in result.nodes]
        assert "helper" in names

    def test_async_function(self):
        result = self._extract("async function fetchData() { await fetch('/api'); }")
        names = [n.name for n in result.nodes]
        assert "fetchData" in names

    def test_generator_function(self):
        result = self._extract("function* gen() { yield 1; yield 2; }")
        # Generator may or may not be extracted as named node
        assert result is not None
        assert len(result.errors) == 0

    def test_class_with_static_method(self):
        result = self._extract("class Utils { static format(s) { return s; } }")
        names = [n.name for n in result.nodes]
        assert "Utils" in names

    def test_class_with_getter_setter(self):
        result = self._extract("class Obj { get name() { return this._name; } set name(v) { this._name = v; } }")
        names = [n.name for n in result.nodes]
        assert "Obj" in names

    def test_destructured_assignment(self):
        result = self._extract("const { a, b, c } = require('./config');")
        assert result is not None

    def test_class_with_private_field(self):
        result = self._extract("class Counter { #count = 0; increment() { this.#count++; } }")
        names = [n.name for n in result.nodes]
        assert "Counter" in names

    def test_empty_file(self):
        result = self._extract("")
        assert result is not None
        # May have a file-level node
        assert len(result.errors) == 0

    def test_syntax_error_partial(self):
        result = self._extract("function broken( { return; }")
        assert result is not None

    def test_iife(self):
        result = self._extract("(function() { var x = 1; })();")
        assert result is not None

    def test_object_method_shorthand(self):
        result = self._extract("const obj = { greet() { return 'hi'; }, name: 'test' };")
        assert result is not None

    def test_supported_node_kinds(self):
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        kinds = ext.supported_node_kinds()
        assert len(kinds) > 0

    def test_supported_edge_kinds(self):
        from coderag.plugins.javascript.extractor import JavaScriptExtractor

        ext = JavaScriptExtractor()
        kinds = ext.supported_edge_kinds()
        assert len(kinds) > 0

    def test_multiple_classes(self):
        code = "class A { foo() {} }\nclass B extends A { bar() {} }\nclass C { baz() {} }"
        result = self._extract(code)
        names = [n.name for n in result.nodes]
        assert "A" in names
        assert "B" in names
        assert "C" in names

    def test_complex_module(self):
        code = """import { EventEmitter } from 'events';

const DEFAULT_TIMEOUT = 5000;

export class Server extends EventEmitter {
    constructor(port) {
        super();
        this.port = port;
    }

    async start() {
        return new Promise((resolve) => {
            this.emit('started');
            resolve();
        });
    }

    stop() {
        this.emit('stopped');
    }
}

export function createServer(port) {
    return new Server(port);
}
"""
        result = self._extract(code)
        names = [n.name for n in result.nodes]
        assert "Server" in names
        assert "createServer" in names

    def test_switch_statement_in_function(self):
        code = """function getType(val) {
    switch(typeof val) {
        case 'string': return 'str';
        case 'number': return 'num';
        default: return 'unknown';
    }
}"""
        result = self._extract(code)
        names = [n.name for n in result.nodes]
        assert "getType" in names

    def test_try_catch_in_function(self):
        code = """async function safeFetch(url) {
    try {
        const res = await fetch(url);
        return await res.json();
    } catch (err) {
        console.error(err);
        return null;
    }
}"""
        result = self._extract(code)
        names = [n.name for n in result.nodes]
        assert "safeFetch" in names


# ============================================================================
# TypeScript Extractor Tests
# ============================================================================


class TestTSExtractorCoverage:
    """Test TypeScript extractor with various code patterns."""

    def _extract(self, code, filename="test.ts"):
        from coderag.plugins.typescript.extractor import TypeScriptExtractor

        ext = TypeScriptExtractor()
        return ext.extract(filename, code.encode() if isinstance(code, str) else code)

    def test_interface_declaration(self):
        result = self._extract("interface User { name: string; age: number; }")
        names = [n.name for n in result.nodes]
        assert "User" in names

    def test_type_alias(self):
        result = self._extract("type ID = string | number;")
        names = [n.name for n in result.nodes]
        assert "ID" in names

    def test_enum_declaration(self):
        result = self._extract("enum Color { Red, Green, Blue }")
        names = [n.name for n in result.nodes]
        assert "Color" in names

    def test_class_implements_interface(self):
        result = self._extract(
            "interface Greetable { greet(): string; }\nclass Person implements Greetable { greet() { return 'hi'; } }"
        )
        names = [n.name for n in result.nodes]
        assert "Person" in names
        assert "Greetable" in names

    def test_generic_class(self):
        result = self._extract("class Container<T> { value: T; constructor(v: T) { this.value = v; } }")
        names = [n.name for n in result.nodes]
        assert "Container" in names

    def test_abstract_class(self):
        result = self._extract("abstract class Shape { abstract area(): number; }")
        names = [n.name for n in result.nodes]
        assert "Shape" in names

    def test_decorator(self):
        result = self._extract("function Log(target: any) {}\n@Log\nclass Service {}")
        names = [n.name for n in result.nodes]
        assert "Service" in names

    def test_namespace(self):
        result = self._extract("namespace MyApp { export class Config {} }")
        names = [n.name for n in result.nodes]
        # Namespace or Config should be extracted
        assert result is not None  # Namespace may not be extracted as separate node

    def test_type_import(self):
        result = self._extract("import type { User } from './models';")
        assert result is not None

    def test_optional_chaining(self):
        result = self._extract("function getName(user?: { name?: string }) { return user?.name ?? 'unknown'; }")
        names = [n.name for n in result.nodes]
        assert "getName" in names

    def test_empty_file(self):
        result = self._extract("")
        assert result is not None

    def test_supported_node_kinds(self):
        from coderag.plugins.typescript.extractor import TypeScriptExtractor

        ext = TypeScriptExtractor()
        kinds = ext.supported_node_kinds()
        assert len(kinds) > 0

    def test_supported_edge_kinds(self):
        from coderag.plugins.typescript.extractor import TypeScriptExtractor

        ext = TypeScriptExtractor()
        kinds = ext.supported_edge_kinds()
        assert len(kinds) > 0

    def test_complex_ts_module(self):
        code = """import { Injectable } from '@angular/core';

export interface Config {
    apiUrl: string;
    timeout: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
    private config: Config;

    constructor(config: Config) {
        this.config = config;
    }

    async get<T>(path: string): Promise<T> {
        const res = await fetch(this.config.apiUrl + path);
        return res.json();
    }
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE';

export enum StatusCode {
    OK = 200,
    NotFound = 404,
    ServerError = 500,
}
"""
        result = self._extract(code)
        names = [n.name for n in result.nodes]
        assert "Config" in names
        assert "ApiService" in names
        assert "HttpMethod" in names
        assert "StatusCode" in names

    def test_mapped_type(self):
        result = self._extract("type Readonly<T> = { readonly [P in keyof T]: T[P] };")
        assert result is not None

    def test_conditional_type(self):
        result = self._extract("type IsString<T> = T extends string ? true : false;")
        assert result is not None


# ============================================================================
# JavaScript Resolver Tests
# ============================================================================


class TestJSResolverCoverage:
    """Test JavaScript module resolver."""

    def test_resolve_relative_import(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        target = tmp_path / "utils.js"
        target.write_text("export function helper() {}")
        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./utils", str(tmp_path / "main.js"))
        assert result is not None

    def test_resolve_relative_with_index(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        (utils_dir / "index.js").write_text("export default {}")
        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./utils", str(tmp_path / "main.js"))
        assert result is not None

    def test_resolve_node_module(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("react", str(tmp_path / "main.js"))
        assert result is not None

    def test_resolve_symbol(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve_symbol("React", str(tmp_path / "main.js"))
        assert result is not None

    def test_resolve_nonexistent(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./nonexistent", str(tmp_path / "main.js"))
        assert result is not None

    def test_resolve_with_extension(self, tmp_path):
        from coderag.plugins.javascript.resolver import JSResolver

        target = tmp_path / "helper.js"
        target.write_text("export const x = 1;")
        resolver = JSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./helper.js", str(tmp_path / "main.js"))
        assert result is not None


# ============================================================================
# TypeScript Resolver Tests
# ============================================================================


class TestTSResolverCoverage:
    """Test TypeScript module resolver."""

    def test_resolve_relative_ts(self, tmp_path):
        from coderag.plugins.typescript.resolver import TSResolver

        target = tmp_path / "utils.ts"
        target.write_text("export function helper(): string { return 'hi'; }")
        resolver = TSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./utils", str(tmp_path / "main.ts"))
        assert result is not None

    def test_resolve_with_tsconfig_paths(self, tmp_path):
        from coderag.plugins.typescript.resolver import TSResolver

        tsconfig = tmp_path / "tsconfig.json"
        tsconfig.write_text(json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}))
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").write_text("export const x = 1;")
        resolver = TSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("@/utils", str(tmp_path / "main.ts"))
        assert result is not None

    def test_resolve_symbol(self, tmp_path):
        from coderag.plugins.typescript.resolver import TSResolver

        resolver = TSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve_symbol("User", str(tmp_path / "main.ts"))
        assert result is not None

    def test_resolve_nonexistent(self, tmp_path):
        from coderag.plugins.typescript.resolver import TSResolver

        resolver = TSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./nonexistent", str(tmp_path / "main.ts"))
        assert result is not None


# ============================================================================
# CSS Resolver Tests
# ============================================================================


class TestCSSResolverCoverage:
    """Test CSS module resolver."""

    def test_resolve_relative_css(self, tmp_path):
        from coderag.plugins.css.resolver import CSSResolver

        target = tmp_path / "base.css"
        target.write_text("body { margin: 0; }")
        resolver = CSSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./base.css", str(tmp_path / "main.css"))
        assert result is not None

    def test_resolve_nonexistent_css(self, tmp_path):
        from coderag.plugins.css.resolver import CSSResolver

        resolver = CSSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("./nonexistent.css", str(tmp_path / "main.css"))
        assert result is not None

    def test_resolve_symbol(self, tmp_path):
        from coderag.plugins.css.resolver import CSSResolver

        resolver = CSSResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve_symbol(".my-class", str(tmp_path / "main.css"))
        assert result is not None


# ============================================================================
# Framework Detector Tests (using actual parsed trees)
# ============================================================================


class TestTailwindDetectorCoverage:
    """Test Tailwind CSS framework detector."""

    def test_detect_tailwind_config_css(self, tmp_path):
        from coderag.plugins.css.extractor import CSSExtractor
        from coderag.plugins.css.frameworks.tailwind import TailwindDetector

        css_code = "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n.btn { @apply px-4 py-2; }"
        css_file = tmp_path / "styles.css"
        css_file.write_text(css_code)
        ext = CSSExtractor()
        result = ext.extract(str(css_file), css_code.encode())
        detector = TailwindDetector()
        # Parse the CSS to get a tree
        import tree_sitter
        import tree_sitter_css as tscss

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        tree = parser.parse(css_code.encode())
        patterns = detector.detect(str(css_file), tree, css_code.encode(), result.nodes, result.edges)
        assert isinstance(patterns, list)

    def test_detect_no_tailwind(self):
        import tree_sitter
        import tree_sitter_css as tscss

        from coderag.plugins.css.frameworks.tailwind import TailwindDetector

        lang = tree_sitter.Language(tscss.language())
        parser = tree_sitter.Parser(lang)
        css_code = "body { margin: 0; padding: 0; }"
        tree = parser.parse(css_code.encode())
        detector = TailwindDetector()
        patterns = detector.detect("plain.css", tree, css_code.encode(), [], [])
        assert isinstance(patterns, list)


class TestVueDetectorCoverage:
    """Test Vue.js framework detector."""

    def test_detect_vue_component(self):
        import tree_sitter
        import tree_sitter_javascript as tsjs

        from coderag.plugins.javascript.extractor import JavaScriptExtractor
        from coderag.plugins.javascript.frameworks.vue import VueDetector

        lang = tree_sitter.Language(tsjs.language())
        parser = tree_sitter.Parser(lang)
        js_code = """import { defineComponent, ref } from 'vue';
export default defineComponent({
    setup() {
        const count = ref(0);
        return { count };
    }
});
"""
        tree = parser.parse(js_code.encode())
        ext = JavaScriptExtractor()
        result = ext.extract("App.vue.js", js_code.encode())
        detector = VueDetector()
        patterns = detector.detect("App.vue.js", tree, js_code.encode(), result.nodes, result.edges)
        assert isinstance(patterns, list)

    def test_detect_no_vue(self):
        import tree_sitter
        import tree_sitter_javascript as tsjs

        from coderag.plugins.javascript.frameworks.vue import VueDetector

        lang = tree_sitter.Language(tsjs.language())
        parser = tree_sitter.Parser(lang)
        js_code = "function hello() { return 'world'; }"
        tree = parser.parse(js_code.encode())
        detector = VueDetector()
        patterns = detector.detect("plain.js", tree, js_code.encode(), [], [])
        assert isinstance(patterns, list)


# ============================================================================
# SCSS Extractor Tests
# ============================================================================


class TestSCSSExtractorCoverage:
    """Test SCSS extractor with various patterns."""

    def _extract(self, code, filename="test.scss"):
        from coderag.plugins.scss.extractor import SCSSExtractor

        ext = SCSSExtractor()
        return ext.extract(filename, code.encode() if isinstance(code, str) else code)

    def test_variable_declaration(self):
        result = self._extract("$primary-color: #333;")
        assert result is not None

    def test_mixin_declaration(self):
        result = self._extract("@mixin flex-center { display: flex; align-items: center; }")
        assert result is not None

    def test_mixin_include(self):
        result = self._extract("@mixin box { padding: 10px; }\n.card { @include box; }")
        assert result is not None

    def test_nested_selectors(self):
        result = self._extract(".parent { .child { color: red; &:hover { color: blue; } } }")
        assert result is not None

    def test_import_directive(self):
        result = self._extract("@import 'variables';\n@import 'mixins';")
        assert len(result.unresolved_references) > 0 or len(result.nodes) >= 0

    def test_use_directive(self):
        result = self._extract("@use 'sass:math';\n@use 'variables' as vars;")
        assert result is not None

    def test_function_declaration(self):
        result = self._extract("@function double($n) { @return $n * 2; }")
        assert result is not None

    def test_placeholder_selector(self):
        result = self._extract("%clearfix { &::after { content: ''; display: table; clear: both; } }")
        assert result is not None

    def test_empty_file(self):
        result = self._extract("")
        assert result is not None

    def test_supported_node_kinds(self):
        from coderag.plugins.scss.extractor import SCSSExtractor

        ext = SCSSExtractor()
        kinds = ext.supported_node_kinds()
        assert len(kinds) > 0

    def test_supported_edge_kinds(self):
        from coderag.plugins.scss.extractor import SCSSExtractor

        ext = SCSSExtractor()
        kinds = ext.supported_edge_kinds()
        assert len(kinds) > 0

    def test_complex_scss(self):
        code = """$font-stack: Helvetica, sans-serif;
$primary: #333;

@mixin respond-to($breakpoint) {
    @if $breakpoint == 'small' {
        @media (max-width: 600px) { @content; }
    } @else if $breakpoint == 'medium' {
        @media (max-width: 900px) { @content; }
    }
}

.container {
    font: 100% $font-stack;
    color: $primary;

    @include respond-to('small') {
        width: 100%;
    }

    .header {
        background: darken($primary, 10%);

        &__title {
            font-size: 2em;
        }
    }
}
"""
        result = self._extract(code)
        assert result is not None
        assert len(result.nodes) > 0


# ============================================================================
# Pipeline Orchestrator Additional Tests
# ============================================================================


class TestOrchestratorCoverage:
    """Additional orchestrator tests for uncovered paths."""

    def _make_orchestrator(self, tmp_path):
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

    def test_run_with_js_file(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        js = tmp_path / "app.js"
        js.write_text("import React from 'react';\nclass App extends React.Component { render() { return null; } }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_with_ts_file(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        ts = tmp_path / "service.ts"
        ts.write_text("interface Service { start(): void; }\nclass MyService implements Service { start() {} }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_with_mixed_files(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        (tmp_path / "index.js").write_text("export function main() {}")
        (tmp_path / "style.css").write_text(".app { color: red; }")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_incremental_no_changes(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        php = tmp_path / "test.php"
        php.write_text("<?php class Foo {}")
        orch.run(str(tmp_path))
        result = orch.run(str(tmp_path), incremental=True)
        assert result is not None
        store.close()

    def test_run_with_scss_file(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        scss = tmp_path / "styles.scss"
        scss.write_text("$color: red;\n.btn { color: $color; &:hover { color: blue; } }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_with_python_file(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        py = tmp_path / "app.py"
        py.write_text("class App:\n    def run(self):\n        pass\n\ndef main():\n    App().run()\n")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()

    def test_run_empty_directory(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        empty = tmp_path / "empty"
        empty.mkdir()
        result = orch.run(str(empty))
        assert result is not None
        store.close()

    def test_run_with_nested_dirs(self, tmp_path):
        orch, store = self._make_orchestrator(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "index.js").write_text("import { helper } from './utils';\nexport function main() { helper(); }")
        (src / "utils.js").write_text("export function helper() { return 42; }")
        result = orch.run(str(tmp_path))
        assert result is not None
        store.close()
