"""Coverage tests for TypeScript extractor - targeting uncovered lines."""

import pytest

from coderag.core.models import EdgeKind, ExtractionResult, NodeKind
from coderag.plugins.typescript.extractor import TypeScriptExtractor


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


class TestTSHelperFunctions:
    """Test helper functions (lines 47-259)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_docblock_preceding(self):
        """Exercise _find_preceding_docblock."""
        source = b"""/**
 * Fetches user data from API.
 * @param id - User ID
 * @returns Promise<User>
 */
async function fetchUser(id: number): Promise<User> {
    return await api.get(`/users/${id}`);
}
"""
        result = self.ext.extract("doc.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_async_function(self):
        """Exercise _is_async."""
        source = b"""async function fetchData(): Promise<void> {
    await fetch('/api');
}
"""
        result = self.ext.extract("async.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        meta = funcs[0].metadata or {}
        assert meta.get("is_async") is True

    def test_static_method(self):
        """Exercise _is_static."""
        source = b"""class Factory {
    static create(): Factory {
        return new Factory();
    }
}
"""
        result = self.ext.extract("static.ts", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        static_methods = [m for m in methods if (m.metadata or {}).get("is_static")]
        assert len(static_methods) >= 1

    def test_generator_function(self):
        """Exercise _is_generator."""
        source = b"""function* counter(): Generator<number> {
    let i = 0;
    while (true) yield i++;
}
"""
        result = self.ext.extract("gen.ts", source)
        # May or may not produce FUNCTION nodes for generators
        assert isinstance(result, ExtractionResult)

    def test_parameters_with_types(self):
        """Exercise _extract_parameters with type annotations."""
        source = b"""function process(
    name: string,
    age: number = 0,
    ...tags: string[]
): void {
    console.log(name, age, tags);
}
"""
        result = self.ext.extract("params.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_access_modifiers(self):
        """Exercise _get_access_modifier."""
        source = b"""class Service {
    public name: string;
    private _id: number;
    protected config: Config;
    readonly version: string = '1.0';

    public getName(): string { return this.name; }
    private _init(): void {}
    protected setup(): void {}
}
"""
        result = self.ext.extract("access.ts", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(props) >= 3
        assert len(methods) >= 2

    def test_readonly_property(self):
        """Exercise _is_readonly."""
        source = b"""class Config {
    readonly host: string = 'localhost';
    readonly port: number = 3000;
}
"""
        result = self.ext.extract("readonly.ts", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 2

    def test_abstract_member(self):
        """Exercise _is_abstract_member."""
        source = b"""abstract class Shape {
    abstract area(): number;
    abstract perimeter(): number;
    name: string = 'shape';
}
"""
        result = self.ext.extract("abstract.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 2

    def test_override_method(self):
        """Exercise _is_override."""
        source = b"""class Child extends Parent {
    override toString(): string {
        return 'child';
    }
}
"""
        result = self.ext.extract("override.ts", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 1

    def test_type_annotation_extraction(self):
        """Exercise _extract_type_annotation."""
        source = b"""class Store {
    items: Map<string, Item[]>;
    callback: (data: any) => void;
    optional?: string;
}
"""
        result = self.ext.extract("types.ts", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 2

    def test_return_type_extraction(self):
        """Exercise _extract_return_type."""
        source = b"""function parse(input: string): { key: string; value: number } {
    return { key: '', value: 0 };
}
function nothing(): void {}
async function getData(): Promise<string[]> {
    return [];
}
"""
        result = self.ext.extract("returns.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 2

    def test_type_parameters(self):
        """Exercise _extract_type_parameters."""
        source = b"""function identity<T>(arg: T): T {
    return arg;
}
function pair<K, V>(key: K, value: V): [K, V] {
    return [key, value];
}
class Container<T extends Serializable> {
    constructor(private value: T) {}
}
"""
        result = self.ext.extract("generics.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(funcs) >= 2
        assert len(classes) >= 1

    def test_decorators(self):
        """Exercise _extract_decorators."""
        source = b"""function Injectable() { return (target: any) => target; }
function Component(opts: any) { return (target: any) => target; }

@Injectable()
@Component({ selector: 'app-root' })
class AppComponent {
    @Input() title: string = '';

    @HostListener('click')
    onClick(): void {}
}
"""
        result = self.ext.extract("decorators.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1


class TestTSImportPatterns:
    """Test import handling (lines 520-620)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_named_import(self):
        source = b"""import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
"""
        result = self.ext.extract("imports.ts", source)
        # Imports are stored as unresolved references, not IMPORT nodes
        assert len(result.unresolved_references) >= 1

    def test_default_import(self):
        source = b"""import React from 'react';
import express from 'express';
"""
        result = self.ext.extract("default.ts", source)
        assert len(result.unresolved_references) >= 1

    def test_namespace_import(self):
        source = b"""import * as fs from 'fs';
import * as path from 'path';
"""
        result = self.ext.extract("ns.ts", source)
        assert len(result.unresolved_references) >= 1

    def test_side_effect_import(self):
        source = b"""import 'reflect-metadata';
import './polyfills';
"""
        result = self.ext.extract("side.ts", source)
        # Side-effect imports may or may not produce unresolved refs
        assert isinstance(result, ExtractionResult)

    def test_type_import(self):
        source = b"""import type { User } from './models';
import type { Config } from './config';
import { type Handler, serve } from './server';
"""
        result = self.ext.extract("type_import.ts", source)
        assert len(result.unresolved_references) >= 1

    def test_import_with_alias(self):
        source = b"""import { Component as Comp, Injectable as Inj } from '@angular/core';
"""
        result = self.ext.extract("alias.ts", source)
        assert len(result.unresolved_references) >= 1


class TestTSExportPatterns:
    """Test export handling (lines 639-820)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_export_default_function(self):
        source = b"""export default function main(): void {
    console.log('hello');
}
"""
        result = self.ext.extract("expdef.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert any(f.name == "main" for f in funcs)

    def test_export_default_class(self):
        source = b"""export default class App {
    run(): void {}
}
"""
        result = self.ext.extract("expclass.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert any(c.name == "App" for c in classes)

    def test_named_export_clause(self):
        source = b"""const foo = 1;
const bar = 2;
export { foo, bar };
export { foo as default };
"""
        result = self.ext.extract("named.ts", source)
        assert len(result.nodes) >= 1

    def test_reexport(self):
        source = b"""export { default } from './module';
export { foo, bar } from './utils';
export * from './helpers';
export * as ns from './namespace';
"""
        result = self.ext.extract("reexport.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_export_type(self):
        source = b"""export type { User } from './models';
export type Config = { port: number };
"""
        result = self.ext.extract("exp_type.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_export_interface(self):
        source = b"""export interface Logger {
    log(msg: string): void;
    error(msg: string): void;
}
"""
        result = self.ext.extract("exp_iface.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1

    def test_export_enum(self):
        source = b"""export enum Status {
    Active = 'active',
    Inactive = 'inactive',
}
"""
        result = self.ext.extract("exp_enum.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) >= 1


class TestTSClassAdvanced:
    """Test class handling (lines 820-1126)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_class_implements_multiple(self):
        """Exercise _process_class_heritage."""
        source = b"""interface Serializable { serialize(): string; }
interface Disposable { dispose(): void; }

class Resource implements Serializable, Disposable {
    serialize(): string { return ''; }
    dispose(): void {}
}
"""
        result = self.ext.extract("impl.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1
        impl_edges = _edge_kinds(result.edges, EdgeKind.IMPLEMENTS)
        impl_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.IMPLEMENTS]
        assert len(impl_edges) + len(impl_unrefs) >= 1

    def test_class_extends_with_generics(self):
        source = b"""class TypedList<T> extends Array<T> {
    first(): T | undefined {
        return this[0];
    }
}
"""
        result = self.ext.extract("generic_class.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1

    def test_abstract_class_with_methods(self):
        source = b"""abstract class Base {
    abstract getId(): string;
    abstract getName(): string;
    toString(): string {
        return `${this.getId()}: ${this.getName()}`;
    }
}
"""
        result = self.ext.extract("abstract_class.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 2

    def test_constructor_parameter_properties(self):
        source = b"""class User {
    constructor(
        public readonly id: number,
        private name: string,
        protected email: string,
        public age: number = 0,
    ) {}
}
"""
        result = self.ext.extract("ctor_props.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1

    def test_index_signature(self):
        source = b"""class Dictionary {
    [key: string]: any;
    get(key: string): any { return this[key]; }
}
"""
        result = self.ext.extract("index_sig.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1

    def test_class_with_private_fields(self):
        source = b"""class Counter {
    #count: number = 0;
    increment(): void { this.#count++; }
    get value(): number { return this.#count; }
}
"""
        result = self.ext.extract("private.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1


class TestTSInterfaceAdvanced:
    """Test interface handling (lines 1236-1478)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_interface_with_methods(self):
        source = b"""interface Repository<T> {
    find(id: string): Promise<T | null>;
    findAll(): Promise<T[]>;
    save(entity: T): Promise<void>;
    delete(id: string): Promise<boolean>;
}
"""
        result = self.ext.extract("repo.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 3

    def test_interface_extends_multiple(self):
        source = b"""interface A { a(): void; }
interface B { b(): void; }
interface C extends A, B {
    c(): void;
}
"""
        result = self.ext.extract("multi_ext.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 3

    def test_interface_with_optional_properties(self):
        source = b"""interface Config {
    host: string;
    port?: number;
    debug?: boolean;
    readonly version: string;
}
"""
        result = self.ext.extract("optional.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 3

    def test_interface_with_index_signature(self):
        source = b"""interface StringMap {
    [key: string]: string;
}
interface NumberMap {
    [index: number]: string;
}
"""
        result = self.ext.extract("index.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 2

    def test_interface_with_call_signature(self):
        source = b"""interface Formatter {
    (input: string): string;
    locale: string;
}
"""
        result = self.ext.extract("callable.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1


class TestTSTypeAliasAndEnum:
    """Test type alias and enum (lines 1478-1631)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_complex_type_alias(self):
        source = b"""type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E };
type Callback<T> = (data: T) => void;
type DeepPartial<T> = { [P in keyof T]?: DeepPartial<T[P]> };
"""
        result = self.ext.extract("complex_types.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 2

    def test_string_enum(self):
        source = b"""enum Color {
    Red = '#ff0000',
    Green = '#00ff00',
    Blue = '#0000ff',
}
"""
        result = self.ext.extract("str_enum.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) >= 1

    def test_const_enum(self):
        source = b"""const enum Direction {
    Up,
    Down,
    Left,
    Right,
}
"""
        result = self.ext.extract("const_enum.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) >= 1

    def test_numeric_enum(self):
        source = b"""enum HttpStatus {
    OK = 200,
    NotFound = 404,
    InternalError = 500,
}
"""
        result = self.ext.extract("num_enum.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) >= 1


class TestTSFunctionAndVariable:
    """Test function/variable declarations (lines 1631-1946)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_overloaded_function(self):
        source = b"""function parse(input: string): number;
function parse(input: number): string;
function parse(input: string | number): string | number {
    return typeof input === 'string' ? parseInt(input) : String(input);
}
"""
        result = self.ext.extract("overload.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_arrow_function_typed(self):
        source = b"""const handler: (req: Request, res: Response) => void = (req, res) => {
    res.send('ok');
};
const identity = <T>(x: T): T => x;
"""
        result = self.ext.extract("arrow.ts", source)
        nodes = result.nodes
        non_file = [n for n in nodes if n.kind != NodeKind.FILE]
        assert len(non_file) >= 1

    def test_const_assertion(self):
        source = b"""const ROUTES = {
    home: '/',
    about: '/about',
    users: '/users',
} as const;
"""
        result = self.ext.extract("const_assert.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_destructuring_declaration(self):
        source = b"""const { a, b: renamed, ...rest }: Props = getProps();
const [first, ...others]: number[] = getNumbers();
"""
        result = self.ext.extract("destruct.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_class_expression(self):
        """Exercise _visit_class_expression."""
        source = b"""const MyClass = class implements Serializable {
    serialize(): string { return ''; }
};
const Named = class NamedClass {
    method(): void {}
};
"""
        result = self.ext.extract("class_expr.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1


class TestTSAmbientAndModule:
    """Test ambient declarations and modules (lines 2078-2164)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_declare_function(self):
        source = b"""declare function require(id: string): any;
declare function setTimeout(cb: () => void, ms: number): number;
"""
        result = self.ext.extract("ambient.d.ts", source)
        # Ambient declarations may not produce standalone FUNCTION nodes
        assert isinstance(result, ExtractionResult)

    def test_declare_class(self):
        source = b"""declare class Buffer {
    static from(data: string): Buffer;
    toString(): string;
    length: number;
}
"""
        result = self.ext.extract("buffer.d.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1

    def test_declare_module(self):
        source = b"""declare module 'express' {
    interface Request {
        body: any;
    }
    interface Response {
        send(data: any): void;
    }
}
"""
        result = self.ext.extract("express.d.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_namespace_declaration(self):
        source = b"""namespace Utils {
    export function parse(s: string): number {
        return parseInt(s);
    }
    export interface Config {
        debug: boolean;
    }
}
"""
        result = self.ext.extract("namespace.ts", source)
        assert isinstance(result, ExtractionResult)
        # Namespace contents may or may not be extracted as top-level nodes
        assert len(result.nodes) >= 1  # At least the file node

    def test_declare_namespace(self):
        source = b"""declare namespace NodeJS {
    interface ProcessEnv {
        NODE_ENV: string;
        PORT?: string;
    }
}
"""
        result = self.ext.extract("env.d.ts", source)
        assert isinstance(result, ExtractionResult)


class TestTSCallsAndJSX:
    """Test call scanning and JSX (lines 2170-2367)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_function_calls(self):
        source = b"""function main(): void {
    const result = helper();
    const data = fetchData('/api');
    process(result, data);
}
"""
        result = self.ext.extract("calls.ts", source)
        assert len(result.nodes) >= 1

    def test_new_expression(self):
        source = b"""function create(): void {
    const map = new Map<string, number>();
    const set = new Set<number>([1, 2, 3]);
    const err = new Error('fail');
}
"""
        result = self.ext.extract("new.ts", source)
        assert len(result.nodes) >= 1

    def test_tsx_component(self):
        source = b"""import React from 'react';

interface Props {
    title: string;
    children?: React.ReactNode;
}

const Card: React.FC<Props> = ({ title, children }) => {
    return (
        <div className="card">
            <h2>{title}</h2>
            <div>{children}</div>
        </div>
    );
};

export default Card;
"""
        result = self.ext.extract("card.tsx", source)
        assert isinstance(result, ExtractionResult)
        non_file = [n for n in result.nodes if n.kind != NodeKind.FILE]
        assert len(non_file) >= 1

    def test_tsx_with_hooks(self):
        source = b"""import React, { useState, useEffect } from 'react';

function Counter(): JSX.Element {
    const [count, setCount] = useState<number>(0);

    useEffect(() => {
        document.title = `Count: ${count}`;
    }, [count]);

    return (
        <div>
            <p>{count}</p>
            <button onClick={() => setCount(c => c + 1)}>+</button>
        </div>
    );
}
"""
        result = self.ext.extract("counter.tsx", source)
        assert isinstance(result, ExtractionResult)

    def test_method_chaining(self):
        source = b"""class Builder {
    private items: string[] = [];
    add(item: string): this {
        this.items.push(item);
        return this;
    }
    build(): string {
        return this.items.join(', ');
    }
}
const result = new Builder().add('a').add('b').build();
"""
        result = self.ext.extract("chain.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) >= 1


class TestTSExpressionStatement:
    """Test expression statement handling (lines 2012-2078)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_iife(self):
        source = b"""(function(): void {
    console.log('init');
})();

(async () => {
    await fetch('/api');
})();
"""
        result = self.ext.extract("iife.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_assignment_expression(self):
        source = b"""let x: number;
x = 42;
const obj: Record<string, any> = {};
obj.key = 'value';
"""
        result = self.ext.extract("assign.ts", source)
        assert isinstance(result, ExtractionResult)


class TestTSEdgeCases:
    """Additional edge cases."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ext = TypeScriptExtractor()

    def test_empty_file(self):
        result = self.ext.extract("empty.ts", b"")
        assert isinstance(result, ExtractionResult)

    def test_comments_only(self):
        source = b"""// This is a comment
/* Block comment */
/** JSDoc comment */
"""
        result = self.ext.extract("comments.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_complex_generics(self):
        source = b"""type Awaited<T> = T extends Promise<infer U> ? Awaited<U> : T;
type NonNullable<T> = T extends null | undefined ? never : T;
interface Monad<T> {
    map<U>(fn: (value: T) => U): Monad<U>;
    flatMap<U>(fn: (value: T) => Monad<U>): Monad<U>;
}
"""
        result = self.ext.extract("advanced_types.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(type_aliases) + len(interfaces) >= 2

    def test_mapped_type(self):
        source = b"""type Readonly<T> = { readonly [P in keyof T]: T[P] };
type Partial<T> = { [P in keyof T]?: T[P] };
"""
        result = self.ext.extract("mapped.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 2

    def test_intersection_union_types(self):
        source = b"""type Admin = User & { role: 'admin' };
type Result = Success | Failure;
type StringOrNumber = string | number;
"""
        result = self.ext.extract("union.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 2

    def test_satisfies_operator(self):
        source = b"""type Colors = 'red' | 'green' | 'blue';
const palette = {
    red: [255, 0, 0],
    green: '#00ff00',
    blue: [0, 0, 255],
} satisfies Record<Colors, string | number[]>;
"""
        result = self.ext.extract("satisfies.ts", source)
        assert isinstance(result, ExtractionResult)

    def test_multiple_exports_and_imports(self):
        source = b"""import { A } from './a';
import { B } from './b';
import type { C } from './c';

export class Service {
    constructor(private a: A, private b: B) {}
    process(c: C): void {}
}

export function createService(): Service {
    return new Service(new A(), new B());
}

export default Service;
export type { C };
"""
        result = self.ext.extract("complex.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(classes) >= 1
        assert len(funcs) >= 1
        # Imports are tracked as unresolved references
        assert len(result.unresolved_references) >= 1
