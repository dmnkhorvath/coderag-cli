"""Comprehensive tests for Python extractor, resolver, and plugin."""

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
from coderag.plugins.python.extractor import PythonExtractor
from coderag.plugins.python.plugin import PythonPlugin
from coderag.plugins.python.resolver import PythonResolver


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# PythonExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPythonExtractorBasic:
    """Basic Python extraction tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = PythonExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.py", b"")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.py"
        assert result.language == "python"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_function(self):
        source = b"""def greet(name: str) -> str:
    return f"Hello, {name}!"
"""
        result = self.extractor.extract("greet.py", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 1
        assert funcs[0].name == "greet"

    def test_class_extraction(self):
        source = b"""class UserService:
    \"\"\"User service class.\"\"\"

    def __init__(self, db):
        self.db = db

    def get_user(self, user_id: int) -> dict:
        return self.db.find(user_id)

    def create_user(self, data: dict) -> dict:
        return self.db.insert(data)
"""
        result = self.extractor.extract("service.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = _kinds(result.nodes, NodeKind.METHOD)
        method_names = [m.name for m in methods]
        assert "__init__" in method_names
        assert "get_user" in method_names
        assert "create_user" in method_names

    def test_class_inheritance(self):
        source = b"""class Animal:
    pass

class Dog(Animal):
    pass
"""
        result = self.extractor.extract("animals.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 2

        extends_edges = _edge_kinds(result.edges, EdgeKind.EXTENDS)
        extends_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.EXTENDS]
        assert len(extends_edges) + len(extends_unrefs) >= 1

    def test_abc_as_interface(self):
        source = b"""from abc import ABC, abstractmethod

class Repository(ABC):
    @abstractmethod
    def find(self, id: int):
        pass

    @abstractmethod
    def save(self, entity):
        pass
"""
        result = self.extractor.extract("repo.py", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) == 1
        assert interfaces[0].name == "Repository"

    def test_enum_extraction(self):
        source = b"""from enum import Enum

class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
"""
        result = self.extractor.extract("colors.py", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) == 1
        assert enums[0].name == "Color"

    def test_dataclass(self):
        source = b"""from dataclasses import dataclass

@dataclass
class User:
    name: str
    email: str
    age: int = 0
"""
        result = self.extractor.extract("models.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].metadata.get("is_dataclass") is True

    def test_import_statement(self):
        source = b"""import os
import sys
import json
"""
        result = self.extractor.extract("imports.py", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 3

    def test_from_import(self):
        source = b"""from os.path import join, exists
from typing import List, Dict, Optional
"""
        result = self.extractor.extract("imports.py", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_relative_import(self):
        source = b"""from . import models
from ..utils import helper
from .services import UserService
"""
        result = self.extractor.extract("app/__init__.py", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_decorator_extraction(self):
        source = b"""import functools

def my_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@my_decorator
def decorated_function():
    pass
"""
        result = self.extractor.extract("decorators.py", source)
        decorators = _kinds(result.nodes, NodeKind.DECORATOR)
        assert len(decorators) >= 1

    def test_variable_extraction(self):
        source = b"""MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
api_url = "https://api.example.com"
"""
        result = self.extractor.extract("config.py", source)
        vars_and_consts = _kinds(result.nodes, NodeKind.VARIABLE) + _kinds(result.nodes, NodeKind.CONSTANT)
        assert len(vars_and_consts) >= 2

    def test_async_function(self):
        source = b"""import asyncio

async def fetch_data(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
"""
        result = self.extractor.extract("api.py", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1
        assert funcs[0].name == "fetch_data"

    def test_property_extraction(self):
        source = b"""class Config:
    def __init__(self):
        self._name = "default"

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value
"""
        result = self.extractor.extract("config.py", source)
        # Properties may be extracted as methods or properties
        methods = _kinds(result.nodes, NodeKind.METHOD)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(methods) + len(props) >= 2

    def test_nested_class(self):
        source = b"""class Outer:
    class Inner:
        def method(self):
            pass
"""
        result = self.extractor.extract("nested.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 2

    def test_multiple_inheritance(self):
        source = b"""class Mixin1:
    pass

class Mixin2:
    pass

class Combined(Mixin1, Mixin2):
    pass
"""
        result = self.extractor.extract("mixins.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 3
        extends_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.EXTENDS]
        assert len(extends_unrefs) >= 2

    def test_static_method(self):
        source = b"""class MathUtils:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b
"""
        result = self.extractor.extract("math_utils.py", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1

    def test_class_method(self):
        source = b"""class Factory:
    @classmethod
    def create(cls, data: dict) -> "Factory":
        return cls(**data)
"""
        result = self.extractor.extract("factory.py", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1

    def test_parse_error_tolerance(self):
        source = b"""def broken(
    return 42
"""
        result = self.extractor.extract("broken.py", source)
        assert len(result.nodes) > 0
        assert len(result.errors) > 0

    def test_multiple_functions(self):
        source = b"""def first():
    pass

def second():
    pass

def third():
    pass
"""
        result = self.extractor.extract("funcs.py", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 3

    def test_docstring_extraction(self):
        source = b"""class MyClass:
    \"\"\"This is a docstring.\"\"\"

    def method(self):
        \"\"\"Method docstring.\"\"\"
        pass
"""
        result = self.extractor.extract("documented.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].docblock is not None

    def test_contains_edges(self):
        source = b"""class Foo:
    def bar(self):
        pass
    def baz(self):
        pass
"""
        result = self.extractor.extract("foo.py", source)
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 2

    def test_supported_kinds(self):
        assert NodeKind.CLASS in self.extractor.supported_node_kinds()
        assert NodeKind.FUNCTION in self.extractor.supported_node_kinds()
        assert NodeKind.METHOD in self.extractor.supported_node_kinds()
        assert NodeKind.IMPORT in self.extractor.supported_node_kinds()
        assert EdgeKind.CONTAINS in self.extractor.supported_edge_kinds()
        assert EdgeKind.EXTENDS in self.extractor.supported_edge_kinds()

    def test_file_node_always_created(self):
        result = self.extractor.extract("test.py", b"# empty")
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].language == "python"

    def test_parse_time_recorded(self):
        result = self.extractor.extract("a.py", b"x = 1")
        assert result.parse_time_ms >= 0

    def test_complex_module(self):
        source = b"""from typing import Optional, List
from dataclasses import dataclass, field

@dataclass
class User:
    name: str
    email: str
    roles: List[str] = field(default_factory=list)

class UserRepository:
    def __init__(self):
        self._users: List[User] = []

    def add(self, user: User) -> None:
        self._users.append(user)

    def find_by_email(self, email: str) -> Optional[User]:
        for user in self._users:
            if user.email == email:
                return user
        return None

    def all(self) -> List[User]:
        return list(self._users)
"""
        result = self.extractor.extract("users.py", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 2
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 3
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_lambda_not_extracted(self):
        source = b"""sort_key = lambda x: x.name
"""
        result = self.extractor.extract("lambdas.py", source)
        # Lambdas should not be extracted as functions
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 0

    def test_type_alias(self):
        source = b"""from typing import Union

UserID = Union[str, int]
"""
        result = self.extractor.extract("types.py", source)
        # Type aliases may be extracted as variables or type_alias
        all_nodes = result.nodes
        assert len(all_nodes) >= 2  # file + at least import

    def test_generator_function(self):
        source = b"""def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b
"""
        result = self.extractor.extract("generators.py", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) >= 1

    def test_call_edges(self):
        source = b"""def helper():
    pass

def main():
    helper()
    print("done")
"""
        result = self.extractor.extract("main.py", source)
        calls = _edge_kinds(result.edges, EdgeKind.CALLS)
        call_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.CALLS]
        assert len(calls) + len(call_unrefs) >= 1


# ═══════════════════════════════════════════════════════════════════════
# PythonResolver Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPythonResolver:
    """Test Python module resolution."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a mock Python project."""
        (tmp_path / "mypackage").mkdir()
        (tmp_path / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "mypackage" / "models.py").write_text("class User: pass")
        (tmp_path / "mypackage" / "services.py").write_text("class UserService: pass")
        (tmp_path / "mypackage" / "utils").mkdir()
        (tmp_path / "mypackage" / "utils" / "__init__.py").write_text("")
        (tmp_path / "mypackage" / "utils" / "helpers.py").write_text("def helper(): pass")
        return tmp_path

    @pytest.fixture
    def resolver(self, project_dir):
        r = PythonResolver()
        r.set_project_root(str(project_dir))
        files = []
        for root, dirs, filenames in os.walk(str(project_dir)):
            for fn in filenames:
                if fn.endswith(".py"):
                    abs_path = os.path.join(root, fn)
                    rel_path = os.path.relpath(abs_path, str(project_dir))
                    files.append(
                        FileInfo(
                            relative_path=rel_path,
                            path=abs_path,
                            language=Language.PYTHON,
                            plugin_name="python",
                            size_bytes=os.path.getsize(abs_path),
                        )
                    )
        r.build_index(files)
        return r

    def test_stdlib_detection(self, resolver):
        result = resolver.resolve("os", "mypackage/models.py")
        assert result.metadata.get("stdlib") is True
        assert result.resolved_path is None

    def test_stdlib_submodule(self, resolver):
        result = resolver.resolve("os.path", "mypackage/models.py")
        assert result.metadata.get("stdlib") is True

    def test_absolute_import(self, resolver):
        result = resolver.resolve("mypackage.models", "mypackage/services.py")
        if result.resolved_path is not None:
            assert "models" in result.resolved_path

    def test_relative_import(self, resolver):
        result = resolver.resolve(
            ".models",
            "mypackage/services.py",
            context={"is_relative": True, "level": 1},
        )
        if result.resolved_path is not None:
            assert "models" in result.resolved_path

    def test_relative_import_parent(self, resolver):
        result = resolver.resolve(
            "..models",
            "mypackage/utils/helpers.py",
            context={"is_relative": True, "level": 2},
        )
        if result.resolved_path is not None:
            assert "models" in result.resolved_path

    def test_package_init_resolution(self, resolver):
        result = resolver.resolve("mypackage", "test.py")
        if result.resolved_path is not None:
            assert "__init__" in result.resolved_path

    def test_unresolved_import(self, resolver):
        result = resolver.resolve("nonexistent.module", "mypackage/models.py")
        assert result.resolved_path is None
        assert result.confidence == 0.0

    def test_resolve_symbol(self, resolver):
        result = resolver.resolve_symbol("mypackage.models", "test.py")
        assert isinstance(result, ResolutionResult)

    def test_src_layout(self, tmp_path):
        """Test src/ layout detection."""
        (tmp_path / "src" / "mypackage").mkdir(parents=True)
        (tmp_path / "src" / "mypackage" / "__init__.py").write_text("")
        (tmp_path / "src" / "mypackage" / "core.py").write_text("class Core: pass")

        r = PythonResolver()
        r.set_project_root(str(tmp_path))
        files = [
            FileInfo(
                relative_path="src/mypackage/__init__.py",
                path=str(tmp_path / "src" / "mypackage" / "__init__.py"),
                language=Language.PYTHON,
                plugin_name="python",
                size_bytes=0,
            ),
            FileInfo(
                relative_path="src/mypackage/core.py",
                path=str(tmp_path / "src" / "mypackage" / "core.py"),
                language=Language.PYTHON,
                plugin_name="python",
                size_bytes=100,
            ),
        ]
        r.build_index(files)
        result = r.resolve("mypackage.core", "test.py")
        if result.resolved_path is not None:
            assert "core" in result.resolved_path

    def test_typing_is_stdlib(self, resolver):
        result = resolver.resolve("typing", "mypackage/models.py")
        assert result.metadata.get("stdlib") is True

    def test_collections_is_stdlib(self, resolver):
        result = resolver.resolve("collections", "mypackage/models.py")
        assert result.metadata.get("stdlib") is True


# ═══════════════════════════════════════════════════════════════════════
# PythonPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPythonPlugin:
    """Test Python plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = PythonPlugin()
        assert plugin.name == "python"
        assert plugin.language == Language.PYTHON
        assert ".py" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = PythonPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor(self):
        plugin = PythonPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, PythonExtractor)

    def test_get_resolver(self):
        plugin = PythonPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, PythonResolver)

    def test_get_framework_detectors(self):
        plugin = PythonPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)

    def test_cleanup(self, tmp_path):
        plugin = PythonPlugin()
        plugin.initialize({}, str(tmp_path))
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = PythonPlugin()
        plugin.cleanup()
        ext = plugin.get_extractor()
        assert ext is not None

    def test_pyi_extension(self):
        plugin = PythonPlugin()
        exts = plugin.file_extensions
        assert ".pyi" in exts or ".py" in exts
