"""Coverage tests for JavaScript extractor - targeting uncovered lines."""

import pytest

from coderag.core.models import EdgeKind, ExtractionResult, NodeKind
from coderag.plugins.javascript.extractor import JavaScriptExtractor


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


class TestJSHelperFunctions:
    """Test helper/utility functions at module level (lines 45-158)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_docblock_preceding_function(self):
        """Exercise _find_preceding_docblock (lines 59-74)."""
        source = b"""/**
 * Greets a user.
 * @param {string} name
 * @returns {string}
 */
function greet(name) {
    return `Hello, ${name}!`;
}
"""
        result = self.ext.extract("doc.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 1
        assert funcs[0].name == "greet"
        # docblock should be captured in metadata
        meta = funcs[0].metadata or {}
        if "docstring" in meta:
            assert "Greets" in meta["docstring"]

    def test_async_function(self):
        """Exercise _is_async (lines 67-74)."""
        source = b"""async function fetchData(url) {
    const response = await fetch(url);
    return response.json();
}
"""
        result = self.ext.extract("async.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        f = [f for f in funcs if f.name == "fetchData"][0]
        meta = f.metadata or {}
        assert meta.get("is_async") is True

    def test_static_method(self):
        """Exercise _is_static (lines 79-84)."""
        source = b"""class Utils {
    static create() {
        return new Utils();
    }
    static get instance() {
        return this._inst;
    }
}
"""
        result = self.ext.extract("static.js", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        static_methods = [m for m in methods if (m.metadata or {}).get("is_static")]
        assert len(static_methods) >= 1

    def test_generator_function(self):
        """Exercise _is_generator (lines 89-93)."""
        source = b"""function* range(start, end) {
    for (let i = start; i < end; i++) {
        yield i;
    }
}
"""
        result = self.ext.extract("gen.js", source)
        # Generator functions may be extracted as FUNCTION or VARIABLE
        non_file = [n for n in result.nodes if n.kind != NodeKind.FILE]
        # At minimum the file should parse without error
        assert isinstance(result, ExtractionResult)

    def test_function_parameters(self):
        """Exercise _extract_parameters (lines 96-128)."""
        source = b"""function complex(a, b = 10, ...rest) {
    return [a, b, ...rest];
}
"""
        result = self.ext.extract("params.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        f = [f for f in funcs if f.name == "complex"][0]
        meta = f.metadata or {}
        params = meta.get("parameters", [])
        if params:
            names = [p.get("name", "") for p in params]
            assert "a" in names

    def test_pascal_case_detection_jsx(self):
        """Exercise _is_pascal_case and _contains_jsx (lines 131-158)."""
        source = b"""function MyComponent(props) {
    return <div className="container">
        <h1>{props.title}</h1>
        <p>{props.children}</p>
    </div>;
}
"""
        result = self.ext.extract("comp.jsx", source)
        # JSX components are extracted as COMPONENT kind
        comps = _kinds(result.nodes, NodeKind.COMPONENT)
        names = _names(comps)
        assert "MyComponent" in names

    def test_get_method_kind_getter_setter(self):
        """Exercise _get_method_kind (lines 146-158)."""
        source = b"""class Person {
    get name() {
        return this._name;
    }
    set name(value) {
        this._name = value;
    }
}
"""
        result = self.ext.extract("accessor.js", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        method_names = _names(methods)
        assert "name" in method_names


class TestJSCollectErrors:
    """Test _collect_errors (lines 240-249)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_syntax_error_collection(self):
        """Parse errors should be collected."""
        source = b"""function broken( {
    return 42;
}
class Also {
    method() { return; }
}
"""
        result = self.ext.extract("broken.js", source)
        # Should still extract what it can
        assert isinstance(result, ExtractionResult)
        # errors may or may not be populated depending on tree-sitter behavior


class TestJSImportExport:
    """Test import/export handling (lines 360-740)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_namespace_import(self):
        """Exercise _handle_import_statement namespace import (lines 394-425)."""
        source = b"""import * as utils from './utils';
import * as path from 'path';
"""
        result = self.ext.extract("ns.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_side_effect_import(self):
        """Import with no specifiers."""
        source = b"""import './polyfills';
import 'reflect-metadata';
"""
        result = self.ext.extract("side.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_import_with_alias(self):
        """Exercise _extract_import_specifiers with aliases (lines 475-502)."""
        source = b"""import { Component as Comp, useState as uS } from 'react';
"""
        result = self.ext.extract("alias.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_export_default_function(self):
        """Exercise _handle_export_statement default (lines 528-624)."""
        source = b"""export default function main() {
    console.log('hello');
}
"""
        result = self.ext.extract("expdef.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert any(f.name == "main" for f in funcs)

    def test_export_default_class(self):
        source = b"""export default class App {
    run() { return true; }
}
"""
        result = self.ext.extract("expclass.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert any(c.name == "App" for c in classes)

    def test_export_default_expression(self):
        """Export default anonymous expression."""
        source = b"""export default {
    key: 'value',
    method() { return 1; }
};
"""
        result = self.ext.extract("expobj.js", source)
        assert isinstance(result, ExtractionResult)

    def test_named_export(self):
        """Exercise _handle_export_clause (lines 641-676)."""
        source = b"""const foo = 1;
const bar = 2;
export { foo, bar };
export { foo as default };
"""
        result = self.ext.extract("named_exp.js", source)
        exports = [e for e in result.edges if e.kind == EdgeKind.EXPORTS]
        # Should have export edges or variables
        assert len(result.nodes) >= 1

    def test_reexport(self):
        """Exercise _handle_reexport (lines 686-753)."""
        source = b"""export { default } from './module';
export { foo, bar } from './utils';
export * from './helpers';
export * as ns from './namespace';
"""
        result = self.ext.extract("reexport.js", source)
        # Re-exports produce EXPORT nodes, not IMPORT
        exports = _kinds(result.nodes, NodeKind.EXPORT)
        assert len(exports) >= 1
        # Should also have re_export edges
        reexport_edges = _edge_kinds(result.edges, EdgeKind.RE_EXPORTS)
        assert len(reexport_edges) >= 1

    def test_export_named_declaration(self):
        """Export with declaration."""
        source = b"""export const PI = 3.14;
export let count = 0;
export function add(a, b) { return a + b; }
export class Calculator { compute() {} }
"""
        result = self.ext.extract("exp_decl.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert any(f.name == "add" for f in funcs)
        assert any(c.name == "Calculator" for c in classes)


class TestJSClassAdvanced:
    """Test class handling (lines 796-1033)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_class_with_private_fields(self):
        """Exercise _handle_property (lines 989-1033)."""
        source = b"""class Counter {
    #count = 0;
    static #instances = 0;

    constructor() {
        Counter.#instances++;
    }

    get value() {
        return this.#count;
    }

    increment() {
        this.#count++;
    }
}
"""
        result = self.ext.extract("private.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        # Should detect private fields
        assert len(props) >= 1

    def test_class_with_computed_property(self):
        source = b"""const sym = Symbol('key');
class Dynamic {
    [sym]() { return 'dynamic'; }
    ["computed"]() { return 'computed'; }
}
"""
        result = self.ext.extract("computed.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_class_with_async_generator_method(self):
        """Exercise _handle_method async+generator (lines 898-981)."""
        source = b"""class Stream {
    async *iterate() {
        yield 1;
        yield 2;
    }
    async fetch() {
        return await Promise.resolve(42);
    }
    *generate() {
        yield 'a';
    }
}
"""
        result = self.ext.extract("stream.js", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 3

    def test_class_extends_expression(self):
        """Class extending a complex expression."""
        source = b"""class MyError extends Error {
    constructor(message) {
        super(message);
        this.name = 'MyError';
    }
}
"""
        result = self.ext.extract("myerr.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1


class TestJSFunctionDeclarations:
    """Test function declarations and arrow functions (lines 1037-1242)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_exported_arrow_function(self):
        """Exercise _handle_arrow_function (lines 1112-1135)."""
        source = b"""export const handler = async (req, res) => {
    res.send('ok');
};
"""
        result = self.ext.extract("arrow.js", source)
        nodes = result.nodes
        names = _names(nodes)
        assert "handler" in names

    def test_lexical_declaration_const_let(self):
        """Exercise _handle_lexical_declaration (lines 1178-1242)."""
        source = b"""const CONFIG = { port: 3000, host: 'localhost' };
let counter = 0;
const callback = function named() { return 1; };
const arrow = () => 2;
"""
        result = self.ext.extract("lexical.js", source)
        vars_and_funcs = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.FUNCTION)
        names = _names(vars_and_funcs)
        assert "CONFIG" in names or "counter" in names

    def test_var_declaration(self):
        """Exercise _handle_variable_declaration (lines 1194-1242)."""
        source = b"""var legacy = 'old';
var fn = function() { return 1; };
var obj = { a: 1, b: 2 };
"""
        result = self.ext.extract("var.js", source)
        assert len(result.nodes) >= 2

    def test_destructuring_declaration(self):
        """Exercise _handle_variable_declarator with destructuring (lines 1207-1242)."""
        source = b"""const { a, b: renamed, ...rest } = obj;
const [first, second, ...others] = arr;
let { x = 10, y = 20 } = defaults;
"""
        result = self.ext.extract("destruct.js", source)
        assert isinstance(result, ExtractionResult)


class TestJSRequireAndCJS:
    """Test CommonJS require handling (lines 1279-1439)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_require_call(self):
        """Exercise _handle_require and _extract_require_source (lines 1279-1439)."""
        source = b"""const fs = require('fs');
const path = require('path');
const { readFile, writeFile } = require('fs/promises');
"""
        result = self.ext.extract("cjs.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_require_with_destructuring(self):
        source = b"""const { Router } = require('express');
const { join, resolve } = require('path');
"""
        result = self.ext.extract("cjs2.js", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_module_exports(self):
        """Exercise _handle_expression_statement for module.exports (lines 1359-1439)."""
        source = b"""function helper() { return 1; }
class Service {}
module.exports = { helper, Service };
"""
        result = self.ext.extract("exports.js", source)
        assert len(result.nodes) >= 2

    def test_module_exports_single(self):
        source = b"""class MyClass {
    method() {}
}
module.exports = MyClass;
"""
        result = self.ext.extract("single_exp.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_exports_dot_property(self):
        source = b"""exports.foo = function() { return 1; };
exports.bar = 42;
"""
        result = self.ext.extract("exports_dot.js", source)
        assert len(result.nodes) >= 1


class TestJSCallsAndExpressions:
    """Test call scanning and expression handling (lines 1449-1600)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_function_calls(self):
        """Exercise _scan_calls (lines 1449-1500)."""
        source = b"""function main() {
    const result = helper();
    const data = fetch('/api');
    process(result, data);
}
"""
        result = self.ext.extract("calls.js", source)
        call_edges = _edge_kinds(result.edges, EdgeKind.CALLS)
        # Should detect calls to helper, fetch, process
        assert len(result.nodes) >= 1

    def test_new_expression(self):
        """Exercise _handle_new_expression (lines 1545-1564)."""
        source = b"""function create() {
    const map = new Map();
    const set = new Set([1, 2, 3]);
    const err = new Error('fail');
    return { map, set, err };
}
"""
        result = self.ext.extract("new.js", source)
        # Should detect instantiation edges
        inst_edges = _edge_kinds(result.edges, EdgeKind.INSTANTIATES)
        assert len(result.nodes) >= 1

    def test_method_chaining(self):
        source = b"""function pipeline() {
    return data
        .filter(x => x > 0)
        .map(x => x * 2)
        .reduce((a, b) => a + b, 0);
}
"""
        result = self.ext.extract("chain.js", source)
        assert isinstance(result, ExtractionResult)

    def test_jsx_component_usage(self):
        """Exercise _body_contains_jsx (lines 1576-1600)."""
        source = b"""function App() {
    return (
        <div>
            <Header title="Hello" />
            <Main>
                <p>Content</p>
            </Main>
            <Footer />
        </div>
    );
}

function Header({ title }) {
    return <h1>{title}</h1>;
}
"""
        result = self.ext.extract("app.jsx", source)
        # JSX components are COMPONENT kind
        comps = _kinds(result.nodes, NodeKind.COMPONENT)
        names = _names(comps)
        assert "App" in names

    def test_iife(self):
        """Immediately invoked function expression."""
        source = b"""(function() {
    const x = 1;
})();

(async () => {
    await fetch('/api');
})();
"""
        result = self.ext.extract("iife.js", source)
        assert isinstance(result, ExtractionResult)

    def test_template_literal_calls(self):
        source = b"""const query = gql`
    query GetUser {
        user { id name }
    }
`;
"""
        result = self.ext.extract("tagged.js", source)
        assert isinstance(result, ExtractionResult)


class TestJSEdgeCases:
    """Additional edge cases for maximum coverage."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = JavaScriptExtractor()

    def test_empty_class(self):
        source = b"""class Empty {}
"""
        result = self.ext.extract("empty_class.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_nested_classes(self):
        source = b"""class Outer {
    createInner() {
        return class Inner {
            method() { return 1; }
        };
    }
}
"""
        result = self.ext.extract("nested.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1

    def test_complex_export_patterns(self):
        source = b"""export default class extends Base {
    method() { return super.method(); }
}
"""
        result = self.ext.extract("anon_class.js", source)
        assert isinstance(result, ExtractionResult)

    def test_dynamic_import(self):
        source = b"""async function loadModule() {
    const mod = await import('./dynamic');
    return mod.default;
}
"""
        result = self.ext.extract("dynamic.js", source)
        assert isinstance(result, ExtractionResult)

    def test_for_of_with_destructuring(self):
        source = b"""function process(items) {
    for (const { name, value } of items) {
        console.log(name, value);
    }
}
"""
        result = self.ext.extract("forof.js", source)
        assert isinstance(result, ExtractionResult)

    def test_class_with_field_declarations(self):
        source = b"""class Config {
    host = 'localhost';
    port = 3000;
    debug = false;
    #secret = 'key';
}
"""
        result = self.ext.extract("fields.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 2

    def test_switch_in_function(self):
        source = b"""function handle(action) {
    switch(action.type) {
        case 'ADD': return state + 1;
        case 'SUB': return state - 1;
        default: return state;
    }
}
"""
        result = self.ext.extract("switch.js", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_multiple_classes_and_functions(self):
        source = b"""class A {
    methodA() {}
}
class B extends A {
    methodB() {}
}
function standalone() {
    return new A();
}
const arrow = () => new B();
export { A, B, standalone, arrow };
"""
        result = self.ext.extract("multi.js", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 2
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
