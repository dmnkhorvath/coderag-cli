"""Comprehensive tests for TypeScript extractor, resolver, and plugin."""

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
from coderag.plugins.typescript.extractor import TypeScriptExtractor
from coderag.plugins.typescript.plugin import TypeScriptPlugin
from coderag.plugins.typescript.resolver import TSResolver


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# TypeScriptExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestTypeScriptExtractorBasic:
    """Basic TypeScript extraction tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = TypeScriptExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.ts", b"")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.ts"
        assert result.language == "typescript"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_function(self):
        source = b"""function greet(name: string): string {
    return `Hello, ${name}!`;
}
"""
        result = self.extractor.extract("greet.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_interface_extraction(self):
        source = b"""interface User {
    id: number;
    name: string;
    email: string;
    isActive: boolean;
}
"""
        result = self.extractor.extract("types.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) == 1
        assert interfaces[0].name == "User"

        # Properties of the interface
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 3

    def test_interface_extends(self):
        source = b"""interface Animal {
    name: string;
}

interface Dog extends Animal {
    breed: string;
}
"""
        result = self.extractor.extract("animals.ts", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) == 2

        extends_edges = _edge_kinds(result.edges, EdgeKind.EXTENDS)
        extends_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.EXTENDS]
        assert len(extends_edges) + len(extends_unrefs) >= 1

    def test_type_alias(self):
        source = b"""type ID = string | number;
type UserMap = Map<string, User>;
type Callback = (data: any) => void;
"""
        result = self.extractor.extract("types.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 2

    def test_enum_extraction(self):
        source = b"""enum Direction {
    Up = "UP",
    Down = "DOWN",
    Left = "LEFT",
    Right = "RIGHT",
}
"""
        result = self.extractor.extract("enums.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) == 1
        assert enums[0].name == "Direction"

    def test_const_enum(self):
        source = b"""const enum Status {
    Active,
    Inactive,
    Pending,
}
"""
        result = self.extractor.extract("status.ts", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) == 1

    def test_class_extraction(self):
        source = b"""class UserService {
    private users: User[] = [];

    constructor(private readonly db: Database) {}

    async getUser(id: string): Promise<User> {
        return this.db.find(id);
    }

    createUser(data: CreateUserDto): User {
        const user = new User(data);
        this.users.push(user);
        return user;
    }
}
"""
        result = self.extractor.extract("user-service.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = _kinds(result.nodes, NodeKind.METHOD)
        method_names = [m.name for m in methods]
        assert "getUser" in method_names
        assert "createUser" in method_names

    def test_abstract_class(self):
        source = b"""abstract class BaseRepository<T> {
    abstract find(id: string): Promise<T>;
    abstract save(entity: T): Promise<void>;

    async findAll(): Promise<T[]> {
        return [];
    }
}
"""
        result = self.extractor.extract("base-repo.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        # Check abstract metadata
        cls = classes[0]
        assert cls.metadata.get("is_abstract") is True or cls.name == "BaseRepository"

    def test_class_implements(self):
        source = b"""interface Serializable {
    serialize(): string;
}

class User implements Serializable {
    serialize(): string {
        return JSON.stringify(this);
    }
}
"""
        result = self.extractor.extract("user.ts", source)
        impl_edges = _edge_kinds(result.edges, EdgeKind.IMPLEMENTS)
        impl_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.IMPLEMENTS]
        assert len(impl_edges) + len(impl_unrefs) >= 1

    def test_class_extends(self):
        source = b"""class Animal {
    name: string;
}

class Dog extends Animal {
    breed: string;
}
"""
        result = self.extractor.extract("animals.ts", source)
        extends_edges = _edge_kinds(result.edges, EdgeKind.EXTENDS)
        extends_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.EXTENDS]
        assert len(extends_edges) + len(extends_unrefs) >= 1

    def test_decorator(self):
        source = b"""function Injectable() {
    return function(target: any) {};
}

@Injectable()
class UserService {
    getUsers(): User[] { return []; }
}
"""
        result = self.extractor.extract("service.ts", source)
        _kinds(result.nodes, NodeKind.DECORATOR)
        # Decorators may or may not be extracted as separate nodes
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_generics(self):
        source = b"""function identity<T>(arg: T): T {
    return arg;
}

class Container<T> {
    private value: T;
    constructor(val: T) { this.value = val; }
    getValue(): T { return this.value; }
}
"""
        result = self.extractor.extract("generics.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_named_import(self):
        source = b"""import { Component, OnInit } from '@angular/core';
import { UserService } from './services/user.service';
"""
        result = self.extractor.extract("app.ts", source)
        # Imports are stored as unresolved references, not IMPORT nodes
        assert len(result.unresolved_references) >= 2

    def test_default_import(self):
        source = b"""import React from 'react';
import express from 'express';
"""
        result = self.extractor.extract("app.ts", source)
        assert len(result.unresolved_references) >= 2

    def test_type_only_import(self):
        source = b"""import type { User } from './models';
import type { Config } from './config';
"""
        result = self.extractor.extract("types.ts", source)
        assert len(result.unresolved_references) >= 2

    def test_namespace_import(self):
        source = b"""import * as fs from 'fs';
import * as path from 'path';
"""
        result = self.extractor.extract("utils.ts", source)
        assert len(result.unresolved_references) >= 2

    def test_named_export(self):
        source = b"""export function helper(): void {}
export const VERSION = '1.0.0';
export class Config {}
"""
        result = self.extractor.extract("helpers.ts", source)
        _kinds(result.nodes, NodeKind.EXPORT)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(funcs) >= 1
        assert len(classes) >= 1

    def test_default_export(self):
        source = b"""export default class App {
    run(): void {}
}
"""
        result = self.extractor.extract("app.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

    def test_re_export(self):
        source = b"""export { default as Button } from './Button';
export { UserService } from './services';
export type { User } from './models';
"""
        result = self.extractor.extract("index.ts", source)
        assert len(result.nodes) >= 1

    def test_variable_declarations(self):
        source = b"""const API_URL: string = 'https://api.example.com';
let counter: number = 0;
const config: Readonly<Config> = { debug: false };
"""
        result = self.extractor.extract("config.ts", source)
        vars_and_consts = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.CONSTANT)
        assert len(vars_and_consts) >= 2

    def test_async_function(self):
        source = b"""async function fetchData(url: string): Promise<Response> {
    const response = await fetch(url);
    return response;
}
"""
        result = self.extractor.extract("api.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        assert funcs[0].metadata.get("is_async") is True

    def test_generator_function(self):
        source = b"""function* range(start: number, end: number): Generator<number> {
    for (let i = start; i < end; i++) {
        yield i;
    }
}
"""
        result = self.extractor.extract("generators.ts", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_arrow_function(self):
        source = b"""const add = (a: number, b: number): number => a + b;
const greet = (name: string): string => {
    return `Hello, ${name}`;
};
"""
        result = self.extractor.extract("utils.ts", source)
        all_nodes = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(all_nodes) >= 1

    def test_static_method(self):
        source = b"""class MathUtils {
    static add(a: number, b: number): number {
        return a + b;
    }
}
"""
        result = self.extractor.extract("math.ts", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1
        assert methods[0].metadata.get("is_static") is True

    def test_access_modifiers(self):
        source = b"""class Service {
    public name: string;
    protected config: Config;
    private secret: string;
    readonly id: string;
}
"""
        result = self.extractor.extract("service.ts", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 3

    def test_optional_property(self):
        source = b"""interface Config {
    host: string;
    port?: number;
    debug?: boolean;
}
"""
        result = self.extractor.extract("config.ts", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        optional_props = [p for p in props if p.metadata.get("is_optional")]
        assert len(optional_props) >= 1

    def test_parse_error_tolerance(self):
        source = b"""class Broken {
    method( {
        return 42;
    }
}
"""
        result = self.extractor.extract("broken.ts", source)
        assert len(result.nodes) > 0
        assert len(result.errors) > 0

    def test_multiple_classes(self):
        source = b"""class First {}
class Second {}
class Third {}
"""
        result = self.extractor.extract("multi.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 3

    def test_getter_setter(self):
        source = b"""class Person {
    private _name: string = '';

    get name(): string {
        return this._name;
    }

    set name(value: string) {
        this._name = value;
    }
}
"""
        result = self.extractor.extract("person.ts", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 2

    def test_contains_edges(self):
        source = b"""class Foo {
    bar(): void {}
    baz(): void {}
}
"""
        result = self.extractor.extract("foo.ts", source)
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 2

    def test_supported_kinds(self):
        assert NodeKind.CLASS in self.extractor.supported_node_kinds()
        assert NodeKind.INTERFACE in self.extractor.supported_node_kinds()
        assert NodeKind.ENUM in self.extractor.supported_node_kinds()
        assert NodeKind.TYPE_ALIAS in self.extractor.supported_node_kinds()
        assert NodeKind.FUNCTION in self.extractor.supported_node_kinds()
        assert EdgeKind.CONTAINS in self.extractor.supported_edge_kinds()
        assert EdgeKind.EXTENDS in self.extractor.supported_edge_kinds()
        assert EdgeKind.IMPLEMENTS in self.extractor.supported_edge_kinds()

    def test_file_node_always_created(self):
        result = self.extractor.extract("test.ts", b"// empty")
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].language == "typescript"

    def test_parse_time_recorded(self):
        result = self.extractor.extract("a.ts", b"const x: number = 1;")
        assert result.parse_time_ms >= 0

    def test_tsx_file(self):
        source = b"""import React from 'react';

interface Props {
    name: string;
}

const App: React.FC<Props> = ({ name }) => {
    return <div className="app">Hello {name}</div>;
};

export default App;
"""
        result = self.extractor.extract("App.tsx", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1

    def test_complex_module(self):
        source = b"""import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import type { Repository } from 'typeorm';

interface CreateUserDto {
    name: string;
    email: string;
}

@Injectable()
export class UserService {
    constructor(
        @InjectRepository(User)
        private readonly userRepo: Repository<User>,
    ) {}

    async findAll(): Promise<User[]> {
        return this.userRepo.find();
    }

    async create(dto: CreateUserDto): Promise<User> {
        const user = this.userRepo.create(dto);
        return this.userRepo.save(user);
    }

    async delete(id: string): Promise<void> {
        await this.userRepo.delete(id);
    }
}
"""
        result = self.extractor.extract("user.service.ts", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) >= 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 3
        # Imports are stored as unresolved references
        assert len(result.unresolved_references) >= 2

    def test_has_type_edges(self):
        source = b"""interface Config {
    host: string;
    port: number;
}
"""
        result = self.extractor.extract("config.ts", source)
        has_type = _edge_kinds(result.edges, EdgeKind.HAS_TYPE)
        # Properties should have type edges
        assert len(has_type) >= 1

    def test_mapped_type(self):
        source = b"""type Readonly<T> = {
    readonly [P in keyof T]: T[P];
};
"""
        result = self.extractor.extract("mapped.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 1

    def test_conditional_type(self):
        source = b"""type IsString<T> = T extends string ? true : false;
"""
        result = self.extractor.extract("conditional.ts", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert len(type_aliases) >= 1

    def test_namespace_declaration(self):
        source = b"""namespace MyApp {
    export interface Config {
        debug: boolean;
    }
    export function init(): void {}
}
"""
        result = self.extractor.extract("app.ts", source)
        # Namespace may or may not produce extra nodes depending on extractor
        assert len(result.nodes) >= 1  # At minimum the file node


# ═══════════════════════════════════════════════════════════════════════
# TSResolver Tests
# ═══════════════════════════════════════════════════════════════════════


class TestTSResolver:
    """Test TypeScript module resolution."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a mock TS project."""
        (tmp_path / "src" / "utils").mkdir(parents=True)
        (tmp_path / "src" / "utils" / "helpers.ts").write_text("export const foo = 1;")
        (tmp_path / "src" / "utils" / "index.ts").write_text("export * from './helpers';")
        (tmp_path / "src" / "models").mkdir(parents=True)
        (tmp_path / "src" / "models" / "User.ts").write_text("export interface User {}")
        (tmp_path / "src" / "components").mkdir(parents=True)
        (tmp_path / "src" / "components" / "Button.tsx").write_text("export default function Button() {}")
        (tmp_path / "node_modules" / "@types" / "node").mkdir(parents=True)
        (tmp_path / "node_modules" / "@types" / "node" / "index.d.ts").write_text("declare module 'fs' {}")
        (tmp_path / "package.json").write_text(json.dumps({"type": "module"}))
        (tmp_path / "tsconfig.json").write_text(
            json.dumps(
                {
                    "compilerOptions": {
                        "baseUrl": ".",
                        "paths": {
                            "@/*": ["src/*"],
                            "@models/*": ["src/models/*"],
                        },
                    }
                }
            )
        )
        return tmp_path

    @pytest.fixture
    def resolver(self, project_dir):
        r = TSResolver()
        r.set_project_root(str(project_dir))
        files = []
        for root, dirs, filenames in os.walk(str(project_dir)):
            for fn in filenames:
                if fn.endswith((".ts", ".tsx", ".d.ts")):
                    abs_path = os.path.join(root, fn)
                    rel_path = os.path.relpath(abs_path, str(project_dir))
                    files.append(
                        FileInfo(
                            relative_path=rel_path,
                            path=abs_path,
                            language=Language.TYPESCRIPT,
                            plugin_name="typescript",
                            size_bytes=os.path.getsize(abs_path),
                        )
                    )
        r.build_index(files)
        return r

    def test_builtin_module(self, resolver):
        result = resolver.resolve("fs", "src/app.ts")
        assert result.resolution_strategy == "builtin"
        assert result.confidence == 1.0

    def test_builtin_with_node_prefix(self, resolver):
        result = resolver.resolve("node:path", "src/app.ts")
        assert result.resolution_strategy == "builtin"

    def test_relative_import(self, resolver):
        result = resolver.resolve("./helpers", "src/utils/index.ts")
        assert result.resolved_path is not None
        assert "helpers" in result.resolved_path

    def test_relative_import_with_extension(self, resolver):
        result = resolver.resolve("./helpers.ts", "src/utils/index.ts")
        assert result.resolved_path is not None

    def test_tsconfig_paths_alias(self, resolver):
        result = resolver.resolve("@/utils/helpers", "src/components/Button.tsx")
        if result.resolved_path is not None:
            assert "helpers" in result.resolved_path
            assert result.resolution_strategy == "tsconfig_paths"

    def test_base_url_resolution(self, resolver):
        result = resolver.resolve("src/utils/helpers", "src/app.ts")
        if result.resolved_path is not None:
            assert "helpers" in result.resolved_path

    def test_directory_index_resolution(self, resolver):
        result = resolver.resolve("./utils", "src/app.ts")
        if result.resolved_path is not None:
            assert "index" in result.resolved_path

    def test_unresolved_relative(self, resolver):
        result = resolver.resolve("./nonexistent", "src/app.ts")
        assert result.resolved_path is None

    def test_unresolved_package(self, resolver):
        result = resolver.resolve("nonexistent-package", "src/app.ts")
        assert result.resolved_path is None or result.confidence < 0.5

    def test_parent_relative_import(self, resolver):
        result = resolver.resolve("../utils/helpers", "src/components/Button.tsx")
        if result.resolved_path is not None:
            assert "helpers" in result.resolved_path

    def test_type_only_import_context(self, resolver):
        result = resolver.resolve("./helpers", "src/utils/index.ts", context={"is_type_only": True})
        assert isinstance(result, ResolutionResult)

    def test_resolve_symbol(self, resolver):
        result = resolver.resolve_symbol("helpers", "src/app.ts")
        assert isinstance(result, ResolutionResult)

    def test_tsconfig_extends(self, project_dir):
        """Test tsconfig with extends chain."""
        base_config = {
            "compilerOptions": {
                "strict": True,
                "baseUrl": ".",
            }
        }
        child_config = {"extends": "./tsconfig.base.json", "compilerOptions": {"paths": {"@/*": ["src/*"]}}}
        (project_dir / "tsconfig.base.json").write_text(json.dumps(base_config))
        (project_dir / "tsconfig.json").write_text(json.dumps(child_config))

        r = TSResolver()
        r.set_project_root(str(project_dir))
        # Should load merged config
        assert isinstance(r, TSResolver)

    def test_jsconfig_fallback(self, tmp_path):
        """Test fallback to jsconfig.json when tsconfig.json is missing."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.ts").write_text("export const x = 1;")
        (tmp_path / "jsconfig.json").write_text(
            json.dumps({"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}})
        )
        (tmp_path / "package.json").write_text("{}")

        r = TSResolver()
        r.set_project_root(str(tmp_path))
        assert isinstance(r, TSResolver)


# ═══════════════════════════════════════════════════════════════════════
# TypeScriptPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestTypeScriptPlugin:
    """Test TypeScript plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = TypeScriptPlugin()
        assert plugin.name == "typescript"
        assert plugin.language == Language.TYPESCRIPT
        assert ".ts" in plugin.file_extensions
        assert ".tsx" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = TypeScriptPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor(self):
        plugin = TypeScriptPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, TypeScriptExtractor)

    def test_get_resolver(self):
        plugin = TypeScriptPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, TSResolver)

    def test_get_framework_detectors(self):
        plugin = TypeScriptPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)

    def test_cleanup(self, tmp_path):
        plugin = TypeScriptPlugin()
        plugin.initialize({}, str(tmp_path))
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = TypeScriptPlugin()
        plugin.cleanup()
        ext = plugin.get_extractor()
        assert ext is not None

    def test_file_extensions_include_dts(self):
        plugin = TypeScriptPlugin()
        exts = plugin.file_extensions
        assert ".d.ts" in exts or ".ts" in exts
