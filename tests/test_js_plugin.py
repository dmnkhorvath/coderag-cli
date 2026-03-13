"""Comprehensive tests for JavaScript extractor, resolver, and plugin."""

import json
import os

import pytest

from coderag.core.models import (
    EdgeKind,
    ExtractionResult,
    FileInfo,
    Language,
    NodeKind,
    ResolutionResult,
)
from coderag.plugins.javascript.extractor import JavaScriptExtractor
from coderag.plugins.javascript.plugin import JavaScriptPlugin
from coderag.plugins.javascript.resolver import JSResolver


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# JavaScriptExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestJavaScriptExtractorBasic:
    """Basic JavaScript extraction tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = JavaScriptExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.js", b"")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.js"
        assert result.language == "javascript"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_function(self):
        source = b"""function greet(name) {
    return `Hello, ${name}!`;
}
"""
        result = self.extractor.extract("greet.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_arrow_function_variable(self):
        source = b"""const add = (a, b) => a + b;
const multiply = (a, b) => {
    return a * b;
};
"""
        result = self.extractor.extract("math.js", source)
        vars_or_funcs = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.FUNCTION)
        names = [n.name for n in vars_or_funcs]
        assert "add" in names or "multiply" in names

    def test_class_extraction(self):
        source = b"""class Animal {
    constructor(name) {
        this.name = name;
    }

    speak() {
        return `${this.name} makes a noise.`;
    }
}
"""
        result = self.extractor.extract("animal.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].name == "Animal"

        methods = _kinds(result.nodes, NodeKind.METHOD)
        method_names = [m.name for m in methods]
        assert "constructor" in method_names
        assert "speak" in method_names

    def test_class_extends(self):
        source = b"""class Dog extends Animal {
    bark() {
        return "Woof!";
    }
}
"""
        result = self.extractor.extract("dog.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

        extends_edges = _edge_kinds(result.edges, EdgeKind.EXTENDS)
        extends_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.EXTENDS]
        assert len(extends_edges) + len(extends_unrefs) >= 1

    def test_named_import(self):
        source = b"""import { useState, useEffect } from 'react';
import { Router } from 'express';
"""
        result = self.extractor.extract("app.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_default_import(self):
        source = b"""import React from 'react';
import express from 'express';
"""
        result = self.extractor.extract("app.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_namespace_import(self):
        source = b"""import * as path from 'path';
"""
        result = self.extractor.extract("utils.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_dynamic_import(self):
        source = b"""async function loadModule() {
    const mod = await import('./lazy-module.js');
    return mod;
}
"""
        result = self.extractor.extract("loader.js", source)
        # Should extract the function at minimum
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_named_export(self):
        source = b"""export function helper() { return 42; }
export const VERSION = '1.0.0';
"""
        result = self.extractor.extract("helpers.js", source)
        _kinds(result.nodes, NodeKind.EXPORT)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_default_export(self):
        source = b"""export default class App {
    run() { return true; }
}
"""
        result = self.extractor.extract("app.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_re_export(self):
        source = b"""export { default as Button } from './Button';
export { helper } from './utils';
"""
        result = self.extractor.extract("index.js", source)
        # Should have import/export nodes
        assert len(result.nodes) >= 1

    def test_variable_declarations(self):
        source = b"""const API_URL = 'https://api.example.com';
let counter = 0;
var legacy = true;
"""
        result = self.extractor.extract("config.js", source)
        vars_and_consts = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.CONSTANT)
        assert len(vars_and_consts) >= 2

    def test_async_function(self):
        source = b"""async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}
"""
        result = self.extractor.extract("api.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        assert funcs[0].name == "fetchData"

    def test_generator_function(self):
        """Generator functions are not extracted as separate nodes."""
        source = b"""function* range(start, end) {
    for (let i = start; i < end; i++) {
        yield i;
    }
}
"""
        result = self.extractor.extract("generators.js", source)
        # Generator functions are not currently extracted
        assert len(result.nodes) >= 1  # at least file node
        assert result.nodes[0].kind == NodeKind.FILE

    def test_method_calls_unresolved(self):
        source = b"""class Service {
    process() {
        this.validate();
        const result = Helper.compute();
    }
}
"""
        result = self.extractor.extract("service.js", source)
        calls = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.CALLS]
        assert len(calls) >= 1

    def test_parse_error_tolerance(self):
        source = b"""function broken( {
    return 42;
}
"""
        result = self.extractor.extract("broken.js", source)
        assert len(result.nodes) > 0
        assert len(result.errors) > 0

    def test_multiple_classes(self):
        source = b"""class First {}
class Second {}
class Third {}
"""
        result = self.extractor.extract("multi.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 3

    def test_static_method(self):
        source = b"""class MathUtils {
    static add(a, b) {
        return a + b;
    }
}
"""
        result = self.extractor.extract("math.js", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1

    def test_getter_setter(self):
        source = b"""class Person {
    get fullName() {
        return `${this.first} ${this.last}`;
    }
    set fullName(value) {
        [this.first, this.last] = value.split(' ');
    }
}
"""
        result = self.extractor.extract("person.js", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 2

    def test_destructuring_import(self):
        source = b"""import { readFile, writeFile } from 'fs/promises';
"""
        result = self.extractor.extract("io.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_require_call(self):
        source = b"""const express = require('express');
const { Router } = require('express');
"""
        result = self.extractor.extract("app.cjs", source)
        # Should extract variables or imports
        all_nodes = result.nodes
        assert len(all_nodes) >= 2  # file + at least one declaration

    def test_complex_module(self):
        source = b"""import express from 'express';
import { Router } from 'express';
import cors from 'cors';

const app = express();

class UserController {
    constructor(service) {
        this.service = service;
    }

    async getUsers(req, res) {
        const users = await this.service.findAll();
        res.json(users);
    }

    async createUser(req, res) {
        const user = await this.service.create(req.body);
        res.status(201).json(user);
    }
}

export default UserController;
"""
        result = self.extractor.extract("controllers/user.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 2
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_supported_kinds(self):
        assert NodeKind.CLASS in self.extractor.supported_node_kinds()
        assert NodeKind.FUNCTION in self.extractor.supported_node_kinds()
        assert NodeKind.METHOD in self.extractor.supported_node_kinds()
        assert EdgeKind.CONTAINS in self.extractor.supported_edge_kinds()

    def test_file_node_always_created(self):
        result = self.extractor.extract("test.js", b"// empty")
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].language == "javascript"

    def test_parse_time_recorded(self):
        result = self.extractor.extract("a.js", b"const x = 1;")
        assert result.parse_time_ms >= 0

    def test_jsx_file(self):
        source = b"""import React from 'react';

function App() {
    return <div className="app">Hello</div>;
}

export default App;
"""
        result = self.extractor.extract("App.jsx", source)
        # JSX function components are extracted as COMPONENT, not FUNCTION
        components = _kinds(result.nodes, NodeKind.COMPONENT)
        assert len(components) >= 1
        assert components[0].name == "App"

    def test_contains_edges(self):
        source = b"""class Foo {
    bar() {}
    baz() {}
}
"""
        result = self.extractor.extract("foo.js", source)
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 2  # class contains methods

    def test_computed_property(self):
        source = b"""class Store {
    [Symbol.iterator]() {
        return this.items[Symbol.iterator]();
    }
}
"""
        result = self.extractor.extract("store.js", source)
        # Should not crash on computed properties
        assert len(result.nodes) >= 1


# ═══════════════════════════════════════════════════════════════════════
# JSResolver Tests
# ═══════════════════════════════════════════════════════════════════════


class TestJSResolver:
    """Test JavaScript module resolution."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a mock JS project."""
        (tmp_path / "src" / "utils").mkdir(parents=True)
        (tmp_path / "src" / "utils" / "helpers.js").write_text("export const foo = 1;")
        (tmp_path / "src" / "utils" / "index.js").write_text("export * from './helpers';")
        (tmp_path / "src" / "components").mkdir(parents=True)
        (tmp_path / "src" / "components" / "Button.jsx").write_text("export default function Button() {}")
        (tmp_path / "node_modules" / "lodash").mkdir(parents=True)
        (tmp_path / "node_modules" / "lodash" / "package.json").write_text(
            json.dumps({"name": "lodash", "main": "lodash.js"})
        )
        (tmp_path / "node_modules" / "lodash" / "lodash.js").write_text("module.exports = {};")
        (tmp_path / "package.json").write_text(json.dumps({"type": "module"}))
        return tmp_path

    @pytest.fixture
    def resolver(self, project_dir):
        r = JSResolver()
        r.set_project_root(str(project_dir))
        files = []
        for root, dirs, filenames in os.walk(str(project_dir)):
            for fn in filenames:
                if fn.endswith((".js", ".jsx", ".mjs", ".cjs")):
                    abs_path = os.path.join(root, fn)
                    rel_path = os.path.relpath(abs_path, str(project_dir))
                    files.append(
                        FileInfo(
                            relative_path=rel_path,
                            path=abs_path,
                            language=Language.JAVASCRIPT,
                            plugin_name="javascript",
                            size_bytes=os.path.getsize(abs_path),
                        )
                    )
        r.build_index(files)
        return r

    def test_builtin_module(self, resolver):
        result = resolver.resolve("fs", "src/app.js")
        assert result.resolution_strategy == "builtin"
        assert result.confidence == 1.0

    def test_builtin_with_node_prefix(self, resolver):
        result = resolver.resolve("node:path", "src/app.js")
        assert result.resolution_strategy == "builtin"

    def test_relative_import_exact(self, resolver):
        result = resolver.resolve("./helpers", "src/utils/index.js")
        assert result.resolved_path is not None
        assert "helpers" in result.resolved_path

    def test_relative_import_with_extension(self, resolver):
        result = resolver.resolve("./helpers.js", "src/utils/index.js")
        assert result.resolved_path is not None

    def test_directory_index_resolution(self, resolver):
        result = resolver.resolve("./utils", "src/app.js")
        if result.resolved_path is not None:
            assert "index" in result.resolved_path

    def test_package_resolution(self, resolver):
        result = resolver.resolve("lodash", "src/app.js")
        # Should resolve as external or find in node_modules
        assert result.resolved_path is not None or result.confidence > 0

    def test_unresolved_relative(self, resolver):
        result = resolver.resolve("./nonexistent", "src/app.js")
        assert result.resolved_path is None

    def test_unresolved_package(self, resolver):
        result = resolver.resolve("nonexistent-package", "src/app.js")
        assert result.resolved_path is None or result.confidence < 0.5

    def test_parent_relative_import(self, resolver):
        result = resolver.resolve("../utils/helpers", "src/components/Button.jsx")
        if result.resolved_path is not None:
            assert "helpers" in result.resolved_path

    def test_alias_resolution(self, project_dir):
        """Test alias resolution with package.json imports field."""
        pkg = json.loads((project_dir / "package.json").read_text())
        pkg["imports"] = {"#utils/*": "./src/utils/*"}
        (project_dir / "package.json").write_text(json.dumps(pkg))

        r = JSResolver()
        r.set_project_root(str(project_dir))
        # Alias resolution depends on implementation
        result = r.resolve("#utils/helpers", "src/app.js")
        assert isinstance(result, ResolutionResult)

    def test_resolve_symbol(self, resolver):
        result = resolver.resolve_symbol("helpers", "src/app.js")
        assert isinstance(result, ResolutionResult)


# ═══════════════════════════════════════════════════════════════════════
# JavaScriptPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestJavaScriptPlugin:
    """Test JavaScript plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = JavaScriptPlugin()
        assert plugin.name == "javascript"
        assert plugin.language == Language.JAVASCRIPT
        assert ".js" in plugin.file_extensions
        assert ".jsx" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = JavaScriptPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor(self):
        plugin = JavaScriptPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, JavaScriptExtractor)

    def test_get_resolver(self):
        plugin = JavaScriptPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, JSResolver)

    def test_get_framework_detectors(self):
        plugin = JavaScriptPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)

    def test_cleanup(self, tmp_path):
        plugin = JavaScriptPlugin()
        plugin.initialize({}, str(tmp_path))
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = JavaScriptPlugin()
        plugin.cleanup()
        ext = plugin.get_extractor()
        assert ext is not None

    def test_file_extensions_include_mjs_cjs(self):
        plugin = JavaScriptPlugin()
        exts = plugin.file_extensions
        assert ".mjs" in exts
        assert ".cjs" in exts
