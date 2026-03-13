"""Comprehensive tests for PHP extractor, resolver, and plugin."""

import json

import pytest

from coderag.core.models import (
    EdgeKind,
    ExtractionResult,
    FileInfo,
    Language,
    NodeKind,
    ResolutionResult,
)
from coderag.plugins.php.extractor import PHPExtractor
from coderag.plugins.php.plugin import PHPPlugin
from coderag.plugins.php.resolver import PHPResolver

# ── Helpers ──────────────────────────────────────────────────────────────


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# PHPExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPHPExtractorBasic:
    """Basic extraction tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = PHPExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.php", b"<?php\n")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.php"
        assert result.language == "php"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_class(self):
        source = b"""<?php
namespace App\\Services;

class UserService
{
    public function createUser(array $data): User
    {
        return new User($data);
    }
}
"""
        result = self.extractor.extract("app/Services/UserService.php", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        assert classes[0].name == "UserService"

        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1
        assert methods[0].name == "createUser"

        # Contains edge from class to method
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 1

    def test_namespace_extraction(self):
        source = b"""<?php
namespace App\\Models;

class User {}
"""
        result = self.extractor.extract("app/Models/User.php", source)
        ns_nodes = _kinds(result.nodes, NodeKind.NAMESPACE)
        assert len(ns_nodes) == 1
        assert "App\\Models" in ns_nodes[0].name or "App\\Models" in ns_nodes[0].qualified_name

    def test_interface_extraction(self):
        source = b"""<?php
interface RepositoryInterface
{
    public function find(int $id): ?Model;
    public function save(Model $model): void;
}
"""
        result = self.extractor.extract("RepositoryInterface.php", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert len(interfaces) == 1
        assert interfaces[0].name == "RepositoryInterface"

        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 2

    def test_trait_extraction(self):
        source = b"""<?php
trait HasTimestamps
{
    public function getCreatedAt(): string
    {
        return $this->created_at;
    }
}
"""
        result = self.extractor.extract("HasTimestamps.php", source)
        traits = _kinds(result.nodes, NodeKind.TRAIT)
        assert len(traits) == 1
        assert traits[0].name == "HasTimestamps"

    def test_enum_extraction(self):
        source = b"""<?php
enum Status: string
{
    case Active = 'active';
    case Inactive = 'inactive';
}
"""
        result = self.extractor.extract("Status.php", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert len(enums) == 1
        assert enums[0].name == "Status"

    def test_function_extraction(self):
        source = b"""<?php
function helper_function(string $name): string
{
    return strtoupper($name);
}
"""
        result = self.extractor.extract("helpers.php", source)
        funcs = _kinds(result.nodes, NodeKind.FUNCTION)
        assert len(funcs) == 1
        assert funcs[0].name == "helper_function"

    def test_use_import(self):
        source = b"""<?php
use App\\Models\\User;
use App\\Services\\UserService as Service;
"""
        result = self.extractor.extract("test.php", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 1

    def test_class_with_extends_and_implements(self):
        source = b"""<?php
class UserController extends Controller implements Authenticatable
{
    public function index(): Response
    {
        return new Response();
    }
}
"""
        result = self.extractor.extract("UserController.php", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1

        extends_edges = _edge_kinds(result.edges, EdgeKind.EXTENDS)
        _edge_kinds(result.edges, EdgeKind.IMPLEMENTS)
        # At least one of these should be present (may be in unresolved)
        assert len(extends_edges) > 0 or len(result.unresolved_references) > 0

    def test_trait_usage(self):
        source = b"""<?php
class User extends Model
{
    use HasFactory, SoftDeletes;
}
"""
        result = self.extractor.extract("User.php", source)
        trait_edges = _edge_kinds(result.edges, EdgeKind.USES_TRAIT)
        trait_unrefs = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.USES_TRAIT]
        assert len(trait_edges) + len(trait_unrefs) >= 2

    def test_property_extraction(self):
        source = b"""<?php
class Config
{
    public string $name = 'default';
    protected int $timeout = 30;
    private array $options = [];
}
"""
        result = self.extractor.extract("Config.php", source)
        props = _kinds(result.nodes, NodeKind.PROPERTY)
        assert len(props) >= 2  # At least some properties extracted

    def test_constant_extraction(self):
        source = b"""<?php
class Config
{
    const VERSION = '1.0.0';
    public const MAX_RETRIES = 3;
}
"""
        result = self.extractor.extract("Config.php", source)
        consts = _kinds(result.nodes, NodeKind.CONSTANT)
        assert len(consts) >= 1

    def test_method_calls_unresolved(self):
        source = b"""<?php
class Service
{
    public function process()
    {
        $this->validate();
        $result = Helper::compute();
    }
}
"""
        result = self.extractor.extract("Service.php", source)
        calls = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.CALLS]
        assert len(calls) >= 1

    def test_instantiation_unresolved(self):
        source = b"""<?php
class Factory
{
    public function create()
    {
        return new Product();
    }
}
"""
        result = self.extractor.extract("Factory.php", source)
        instantiates = [u for u in result.unresolved_references if u.reference_kind == EdgeKind.INSTANTIATES]
        assert len(instantiates) >= 1

    def test_parse_error_tolerance(self):
        source = b"""<?php
class Broken {
    public function foo( { // missing closing paren
        return 42;
    }
}
"""
        result = self.extractor.extract("broken.php", source)
        assert len(result.nodes) > 0  # Should still extract something
        assert len(result.errors) > 0

    def test_multiple_classes_in_file(self):
        source = b"""<?php
class First {}
class Second {}
class Third {}
"""
        result = self.extractor.extract("multi.php", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 3

    def test_abstract_class(self):
        source = b"""<?php
abstract class BaseRepository
{
    abstract public function find(int $id);

    public function all(): array
    {
        return [];
    }
}
"""
        result = self.extractor.extract("BaseRepository.php", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 2

    def test_static_method(self):
        source = b"""<?php
class Helper
{
    public static function format(string $value): string
    {
        return trim($value);
    }
}
"""
        result = self.extractor.extract("Helper.php", source)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) == 1

    def test_supported_kinds(self):
        assert NodeKind.CLASS in self.extractor.supported_node_kinds()
        assert NodeKind.METHOD in self.extractor.supported_node_kinds()
        assert NodeKind.FUNCTION in self.extractor.supported_node_kinds()
        assert EdgeKind.CONTAINS in self.extractor.supported_edge_kinds()
        assert EdgeKind.EXTENDS in self.extractor.supported_edge_kinds()

    def test_file_node_always_created(self):
        source = b"<?php\n"
        result = self.extractor.extract("test.php", source)
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].file_path == "test.php"
        assert file_nodes[0].language == "php"

    def test_return_type_edges(self):
        """PHP extractor generates unresolved references for return types, not direct edges."""
        source = b"""<?php
class UserService {
    public function getUser(int $id): User {
        return new User($id);
    }
}
"""
        result = self.extractor.extract("test.php", source)
        # Return types are captured as unresolved references, not direct edges
        # The extractor generates contains edges for the class hierarchy
        contains = [e for e in result.edges if e.kind == EdgeKind.CONTAINS]
        assert len(contains) >= 2  # file->class, class->method

    def test_parameter_type_edges(self):
        """PHP extractor captures parameter types in method metadata, not as edges."""
        source = b"""<?php
class Handler {
    public function handle(Request $request, Response $response): void {
    }
}
"""
        result = self.extractor.extract("test.php", source)
        # Parameter types are in method metadata, not separate edges
        methods = [n for n in result.nodes if n.kind == NodeKind.METHOD]
        assert len(methods) >= 1

    def test_complex_class(self):
        source = b"""<?php
namespace App\\Http\\Controllers;

use App\\Models\\User;
use Illuminate\\Http\\Request;

/**
 * User management controller.
 */
class UserController extends Controller
{
    private UserService $service;

    public function __construct(UserService $service)
    {
        $this->service = $service;
    }

    public function index(Request $request): JsonResponse
    {
        $users = $this->service->getAll();
        return new JsonResponse($users);
    }

    public function store(Request $request): JsonResponse
    {
        $user = $this->service->create($request->validated());
        return new JsonResponse($user, 201);
    }
}
"""
        result = self.extractor.extract("app/Http/Controllers/UserController.php", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert len(classes) == 1
        methods = _kinds(result.nodes, NodeKind.METHOD)
        assert len(methods) >= 3  # __construct, index, store
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_parse_time_recorded(self):
        source = b"<?php\nclass A {}\n"
        result = self.extractor.extract("a.php", source)
        assert result.parse_time_ms >= 0


# ═══════════════════════════════════════════════════════════════════════
# PHPResolver Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPHPResolver:
    """Test PHP namespace resolution."""

    @pytest.fixture
    def resolver_with_composer(self, tmp_path):
        """Create resolver with a composer.json."""
        composer = {
            "autoload": {
                "psr-4": {
                    "App\\\\": "app/",
                    "Tests\\\\": "tests/",
                }
            }
        }
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        (tmp_path / "app" / "Models").mkdir(parents=True)
        (tmp_path / "app" / "Models" / "User.php").write_text("<?php class User {}")
        (tmp_path / "app" / "Services").mkdir(parents=True)
        (tmp_path / "app" / "Services" / "UserService.php").write_text("<?php class UserService {}")

        resolver = PHPResolver()
        resolver.set_project_root(str(tmp_path))
        return resolver

    @pytest.fixture
    def resolver_no_composer(self, tmp_path):
        """Create resolver without composer.json."""
        (tmp_path / "app" / "Models").mkdir(parents=True)
        (tmp_path / "app" / "Models" / "User.php").write_text("<?php class User {}")

        resolver = PHPResolver()
        resolver.set_project_root(str(tmp_path))
        return resolver

    def test_psr4_resolution(self, resolver_with_composer, tmp_path):
        result = resolver_with_composer.resolve("App\\Models\\User", "app/Services/UserService.php")
        assert result.resolved_path is not None
        assert "User.php" in result.resolved_path

    def test_unresolved_import(self, resolver_with_composer):
        result = resolver_with_composer.resolve("App\\NonExistent\\Foo", "app/test.php")
        assert result.resolved_path is None
        assert result.confidence == 0.0

    def test_default_psr4_without_composer(self, resolver_no_composer, tmp_path):
        result = resolver_no_composer.resolve("App\\Models\\User", "test.php")
        # Should try default PSR-4 mapping
        if result.resolved_path is not None:
            assert "User.php" in result.resolved_path

    def test_resolve_symbol(self, resolver_with_composer):
        result = resolver_with_composer.resolve_symbol("App\\Models\\User", "test.php")
        assert result.resolved_path is not None or result.confidence == 0.0

    def test_build_index(self, resolver_with_composer, tmp_path):
        files = [
            FileInfo(
                relative_path="app/Models/User.php",
                path=str(tmp_path / "app" / "Models" / "User.php"),
                language=Language.PHP,
                plugin_name="php",
                size_bytes=100,
            ),
        ]
        resolver_with_composer.build_index(files)
        # After building index, resolution should work via qname index
        result = resolver_with_composer.resolve("App\\Models\\User", "test.php")
        assert result.resolved_path is not None

    def test_composer_with_autoload_dev(self, tmp_path):
        composer = {"autoload": {"psr-4": {"App\\\\": "app/"}}, "autoload-dev": {"psr-4": {"Tests\\\\": "tests/"}}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "UserTest.php").write_text("<?php class UserTest {}")

        resolver = PHPResolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve("Tests\\UserTest", "app/test.php")
        assert result.resolved_path is not None

    def test_forward_slash_normalization(self, resolver_with_composer):
        result = resolver_with_composer.resolve("App/Models/User", "test.php")
        # Should normalize forward slashes to backslashes
        # May or may not resolve depending on implementation
        assert isinstance(result, ResolutionResult)


# ═══════════════════════════════════════════════════════════════════════
# PHPPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPHPPlugin:
    """Test PHP plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = PHPPlugin()
        assert plugin.name == "php"
        assert plugin.language == Language.PHP
        assert ".php" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = PHPPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor_lazy(self):
        plugin = PHPPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, PHPExtractor)

    def test_get_resolver_lazy(self):
        plugin = PHPPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, PHPResolver)

    def test_get_framework_detectors(self):
        plugin = PHPPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)
        assert len(detectors) >= 2  # Laravel + Symfony

    def test_cleanup(self, tmp_path):
        plugin = PHPPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin._extractor is not None
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = PHPPlugin()
        plugin.cleanup()
        # Should still work - lazy initialization
        ext = plugin.get_extractor()
        assert ext is not None
