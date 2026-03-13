"""Tests for Laravel, Symfony, Express, React, and Tailwind framework detectors."""

from __future__ import annotations

import json

from coderag.core.models import (
    Edge,
    EdgeKind,
    FrameworkPattern,
    Node,
    NodeKind,
    generate_node_id,
)
from coderag.plugins.css.frameworks.tailwind import TailwindDetector
from coderag.plugins.javascript.frameworks.express import ExpressDetector
from coderag.plugins.javascript.frameworks.react import ReactDetector
from coderag.plugins.php.frameworks.laravel import LaravelDetector
from coderag.plugins.php.frameworks.symfony import SymfonyDetector

# ── Helpers ───────────────────────────────────────────────────────────


def _make_node(
    file_path: str,
    line: int,
    kind: NodeKind,
    name: str,
    *,
    end_line: int | None = None,
    language: str = "php",
    qualified_name: str | None = None,
    source_text: str | None = None,
) -> Node:
    return Node(
        id=generate_node_id(file_path, line, kind, name),
        kind=kind,
        name=name,
        qualified_name=qualified_name or name,
        file_path=file_path,
        start_line=line,
        end_line=end_line or line + 10,
        language=language,
        source_text=source_text,
    )


def _collect_nodes(patterns: list[FrameworkPattern], kind: NodeKind | None = None) -> list[Node]:
    nodes = []
    for p in patterns:
        for n in p.nodes:
            if kind is None or n.kind == kind:
                nodes.append(n)
    return nodes


def _collect_edges(patterns: list[FrameworkPattern], kind: EdgeKind | None = None) -> list[Edge]:
    edges = []
    for p in patterns:
        for e in p.edges:
            if kind is None or e.kind == kind:
                edges.append(e)
    return edges


# =====================================================================
# LARAVEL DETECTOR TESTS
# =====================================================================


class TestLaravelDetectFramework:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "laravel"

    def test_detects_with_artisan_and_composer(self, tmp_path):
        (tmp_path / "artisan").write_text("#!/usr/bin/env php")
        composer = {"require": {"laravel/framework": "^10.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_artisan_only(self, tmp_path):
        """Artisan alone is enough (likely Laravel)."""
        (tmp_path / "artisan").write_text("#!/usr/bin/env php")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_artisan_and_require_dev(self, tmp_path):
        (tmp_path / "artisan").write_text("#!/usr/bin/env php")
        composer = {"require-dev": {"laravel/framework": "^10.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_artisan_returns_false(self, tmp_path):
        composer = {"require": {"laravel/framework": "^10.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files_returns_false(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_invalid_composer_json(self, tmp_path):
        (tmp_path / "artisan").write_text("#!/usr/bin/env php")
        (tmp_path / "composer.json").write_text("not valid json")
        # Artisan exists, so still True
        assert self.detector.detect_framework(str(tmp_path)) is True


class TestLaravelDetectModel:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_eloquent_model(self):
        source = b"""<?php
namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Model;

class User extends Model
{
    protected $fillable = ['name', 'email'];
    protected $casts = ['email_verified_at' => 'datetime'];
}
"""
        cls_node = _make_node("app/Models/User.php", 6, NodeKind.CLASS, "User", qualified_name="App\\Models\\User")
        target_node = _make_node(
            "vendor/Model.php", 1, NodeKind.CLASS, "Model", qualified_name="Illuminate\\Database\\Eloquent\\Model"
        )
        extends_edge = Edge(
            source_id=cls_node.id,
            target_id=target_node.id,
            kind=EdgeKind.EXTENDS,
            metadata={"target_name": "Model"},
        )
        patterns = self.detector.detect("app/Models/User.php", None, source, [cls_node, target_node], [extends_edge])
        model_nodes = _collect_nodes(patterns, NodeKind.MODEL)
        assert len(model_nodes) >= 1
        assert model_nodes[0].metadata.get("framework") == "laravel"

    def test_detect_authenticatable_model(self):
        source = b"""<?php
namespace App\\Models;

use Illuminate\\Foundation\\Auth\\User as Authenticatable;

class User extends Authenticatable
{
    protected $fillable = ['name', 'email', 'password'];
}
"""
        cls_node = _make_node("app/Models/User.php", 6, NodeKind.CLASS, "User", qualified_name="App\\Models\\User")
        extends_edge = Edge(
            source_id=cls_node.id,
            target_id="__unresolved__:Authenticatable",
            kind=EdgeKind.EXTENDS,
            metadata={"target_name": "Authenticatable"},
        )
        patterns = self.detector.detect("app/Models/User.php", None, source, [cls_node], [extends_edge])
        model_nodes = _collect_nodes(patterns, NodeKind.MODEL)
        assert len(model_nodes) >= 1


class TestLaravelDetectController:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_controller_class(self):
        source = b"""<?php
namespace App\\Http\\Controllers;

class UserController extends Controller
{
    public function index() {}
    public function store() {}
}
"""
        cls_node = _make_node(
            "app/Http/Controllers/UserController.php",
            4,
            NodeKind.CLASS,
            "UserController",
            qualified_name="App\\Http\\Controllers\\UserController",
        )
        target_node = _make_node("vendor/Controller.php", 1, NodeKind.CLASS, "Controller")
        extends_edge = Edge(
            source_id=cls_node.id,
            target_id=target_node.id,
            kind=EdgeKind.EXTENDS,
            metadata={"target_name": "Controller"},
        )
        patterns = self.detector.detect(
            "app/Http/Controllers/UserController.php", None, source, [cls_node, target_node], [extends_edge]
        )
        ctrl_nodes = _collect_nodes(patterns, NodeKind.CONTROLLER)
        assert len(ctrl_nodes) >= 1
        assert ctrl_nodes[0].metadata.get("framework") == "laravel"


class TestLaravelDetectEvent:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_event_class(self):
        source = b"""<?php
namespace App\\Events;

class OrderShipped extends Event
{
    public $order;
}
"""
        cls_node = _make_node(
            "app/Events/OrderShipped.php", 4, NodeKind.CLASS, "OrderShipped", qualified_name="App\\Events\\OrderShipped"
        )
        target_node = _make_node("vendor/Event.php", 1, NodeKind.CLASS, "Event")
        extends_edge = Edge(
            source_id=cls_node.id,
            target_id=target_node.id,
            kind=EdgeKind.EXTENDS,
            metadata={"target_name": "Event"},
        )
        patterns = self.detector.detect(
            "app/Events/OrderShipped.php", None, source, [cls_node, target_node], [extends_edge]
        )
        event_nodes = _collect_nodes(patterns, NodeKind.EVENT)
        assert len(event_nodes) >= 1

    def test_detect_event_by_namespace(self):
        """Events detected by namespace even without extends."""
        source = b"""<?php
namespace App\\Events;

class OrderShipped
{
    public $order;
}
"""
        cls_node = _make_node(
            "app/Events/OrderShipped.php", 4, NodeKind.CLASS, "OrderShipped", qualified_name="App\\Events\\OrderShipped"
        )
        patterns = self.detector.detect("app/Events/OrderShipped.php", None, source, [cls_node], [])
        event_nodes = _collect_nodes(patterns, NodeKind.EVENT)
        assert len(event_nodes) >= 1


class TestLaravelDetectListener:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_listener_by_namespace(self):
        source = b"""<?php
namespace App\\Listeners;

class SendShipmentNotification
{
    public function handle($event) {}
}
"""
        cls_node = _make_node(
            "app/Listeners/SendShipmentNotification.php",
            4,
            NodeKind.CLASS,
            "SendShipmentNotification",
            qualified_name="App\\Listeners\\SendShipmentNotification",
        )
        patterns = self.detector.detect("app/Listeners/SendShipmentNotification.php", None, source, [cls_node], [])
        listener_nodes = _collect_nodes(patterns, NodeKind.LISTENER)
        assert len(listener_nodes) >= 1


class TestLaravelDetectMiddleware:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_middleware_by_namespace(self):
        source = b"""<?php
namespace App\\Http\\Middleware;

class Authenticate
{
    public function handle($request, $next) {}
}
"""
        cls_node = _make_node(
            "app/Http/Middleware/Authenticate.php",
            4,
            NodeKind.CLASS,
            "Authenticate",
            qualified_name="App\\Http\\Middleware\\Authenticate",
        )
        patterns = self.detector.detect("app/Http/Middleware/Authenticate.php", None, source, [cls_node], [])
        mw_nodes = _collect_nodes(patterns, NodeKind.MIDDLEWARE)
        assert len(mw_nodes) >= 1


class TestLaravelDetectServiceProvider:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_detect_service_provider(self):
        source = b"""<?php
namespace App\\Providers;

use Illuminate\\Support\\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register() {}
    public function boot() {}
}
"""
        cls_node = _make_node(
            "app/Providers/AppServiceProvider.php",
            6,
            NodeKind.CLASS,
            "AppServiceProvider",
            qualified_name="App\\Providers\\AppServiceProvider",
        )
        target_node = _make_node("vendor/ServiceProvider.php", 1, NodeKind.CLASS, "ServiceProvider")
        extends_edge = Edge(
            source_id=cls_node.id,
            target_id=target_node.id,
            kind=EdgeKind.EXTENDS,
            metadata={"target_name": "ServiceProvider"},
        )
        patterns = self.detector.detect(
            "app/Providers/AppServiceProvider.php", None, source, [cls_node, target_node], [extends_edge]
        )
        # ServiceProvider should produce some pattern
        assert len(patterns) >= 1


class TestLaravelEmptySource:
    def setup_method(self):
        self.detector = LaravelDetector()

    def test_no_classes_returns_empty(self):
        source = b"<?php\n// empty file\n"
        patterns = self.detector.detect("app/test.php", None, source, [], [])
        assert patterns == []


# =====================================================================
# SYMFONY DETECTOR TESTS
# =====================================================================


class TestSymfonyDetectFramework:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "symfony"

    def test_detects_with_symfony_lock(self, tmp_path):
        (tmp_path / "symfony.lock").write_text("{}")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_bundles_php(self, tmp_path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "bundles.php").write_text("<?php return [];")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_composer_json(self, tmp_path):
        composer = {"require": {"symfony/framework-bundle": "^6.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_require_dev(self, tmp_path):
        composer = {"require-dev": {"symfony/framework-bundle": "^6.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_symfony_returns_false(self, tmp_path):
        composer = {"require": {"laravel/framework": "^10.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files_returns_false(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_invalid_composer_json(self, tmp_path):
        (tmp_path / "composer.json").write_text("not valid json")
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestSymfonyNonPhpFile:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_non_php_file_returns_empty(self):
        source = b"console.log('hello');"
        patterns = self.detector.detect("app.js", None, source, [], [])
        assert patterns == []


class TestSymfonyController:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_controller_extends(self):
        source = b"""<?php
namespace App\\Controller;

use Symfony\\Bundle\\FrameworkBundle\\Controller\\AbstractController;

class UserController extends AbstractController
{
    public function index(): Response {}
}
"""
        cls_node = _make_node("src/Controller/UserController.php", 6, NodeKind.CLASS, "UserController")
        patterns = self.detector.detect("src/Controller/UserController.php", None, source, [cls_node], [])
        ctrl_nodes = _collect_nodes(patterns, NodeKind.CONTROLLER)
        assert len(ctrl_nodes) >= 1
        assert ctrl_nodes[0].metadata.get("framework") == "symfony"


class TestSymfonyRoutes:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_route_attribute(self):
        source = b"""<?php
namespace App\\Controller;

use Symfony\\Component\\Routing\\Attribute\\Route;

class UserController extends AbstractController
{
    #[Route('/users', name: 'user_list', methods: ['GET'])]
    public function index(): Response {}

    #[Route('/users/{id}', name: 'user_show', methods: ['GET', 'POST'])]
    public function show(int $id): Response {}
}
"""
        cls_node = _make_node("src/Controller/UserController.php", 6, NodeKind.CLASS, "UserController")
        method1 = _make_node("src/Controller/UserController.php", 9, NodeKind.METHOD, "index")
        method2 = _make_node("src/Controller/UserController.php", 12, NodeKind.METHOD, "show")
        patterns = self.detector.detect(
            "src/Controller/UserController.php", None, source, [cls_node, method1, method2], []
        )
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) >= 2
        paths = [n.metadata.get("url_pattern") or n.metadata.get("path") for n in route_nodes]
        assert "/users" in paths
        assert "/users/{id}" in paths


class TestSymfonyEntity:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_doctrine_entity(self):
        source = b"""<?php
namespace App\\Entity;

use Doctrine\\ORM\\Mapping as ORM;

#[ORM\\Entity(repositoryClass: UserRepository::class)]
#[ORM\\Table(name: 'users')]
class User
{
    #[ORM\\Id]
    #[ORM\\Column(type: 'integer')]
    private int $id;

    #[ORM\\Column(type: 'string', length: 255)]
    private string $name;
}
"""
        cls_node = _make_node("src/Entity/User.php", 8, NodeKind.CLASS, "User")
        patterns = self.detector.detect("src/Entity/User.php", None, source, [cls_node], [])
        model_nodes = _collect_nodes(patterns, NodeKind.MODEL)
        assert len(model_nodes) >= 1
        assert model_nodes[0].metadata.get("framework") == "symfony"


class TestSymfonyDependencyInjection:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_constructor_injection(self):
        source = b"""<?php
namespace App\\Service;

class UserService
{
    public function __construct(
        private UserRepository $userRepo,
        private LoggerInterface $logger,
    ) {}
}
"""
        cls_node = _make_node("src/Service/UserService.php", 4, NodeKind.CLASS, "UserService")
        patterns = self.detector.detect("src/Service/UserService.php", None, source, [cls_node], [])
        # Should detect DI pattern
        all_edges = _collect_edges(patterns)
        assert len(all_edges) >= 1


class TestSymfonyTemplateReferences:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_render_template(self):
        source = b"""<?php
namespace App\\Controller;

class PageController extends AbstractController
{
    public function index(): Response
    {
        return $this->render('page/index.html.twig', ['title' => 'Home']);
    }
}
"""
        cls_node = _make_node("src/Controller/PageController.php", 4, NodeKind.CLASS, "PageController")
        patterns = self.detector.detect("src/Controller/PageController.php", None, source, [cls_node], [])
        all_edges = _collect_edges(patterns)
        template_edges = [
            e
            for e in all_edges
            if "twig" in str(e.metadata).lower()
            or "template" in str(e.metadata).lower()
            or "twig" in (e.target_id or "").lower()
        ]
        assert len(template_edges) >= 1


class TestSymfonyEvents:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_event_listener(self):
        source = b"""<?php
namespace App\\EventListener;

use Symfony\\Component\\EventDispatcher\\Attribute\\AsEventListener;

#[AsEventListener(event: 'kernel.request')]
class RequestListener
{
    public function __invoke($event) {}
}
"""
        cls_node = _make_node("src/EventListener/RequestListener.php", 7, NodeKind.CLASS, "RequestListener")
        patterns = self.detector.detect("src/EventListener/RequestListener.php", None, source, [cls_node], [])
        event_nodes = _collect_nodes(patterns, NodeKind.EVENT) + _collect_nodes(patterns, NodeKind.LISTENER)
        assert len(event_nodes) >= 1

    def test_detect_event_dispatch(self):
        source = b"""<?php
namespace App\\Service;

class OrderService
{
    public function complete($order)
    {
        $this->dispatcher->dispatch(new OrderCompleted($order));
    }
}
"""
        cls_node = _make_node("src/Service/OrderService.php", 4, NodeKind.CLASS, "OrderService")
        patterns = self.detector.detect("src/Service/OrderService.php", None, source, [cls_node], [])
        all_nodes = _collect_nodes(patterns)
        all_edges = _collect_edges(patterns)
        # Should detect event dispatch
        assert len(all_nodes) + len(all_edges) >= 1


class TestSymfonyFormTypes:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_form_type(self):
        source = b"""<?php
namespace App\\Form;

use Symfony\\Component\\Form\\AbstractType;

class UserType extends AbstractType
{
    public function buildForm($builder, $options) {}
}
"""
        cls_node = _make_node("src/Form/UserType.php", 6, NodeKind.CLASS, "UserType")
        patterns = self.detector.detect("src/Form/UserType.php", None, source, [cls_node], [])
        assert len(patterns) >= 1


class TestSymfonyCommands:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_console_command(self):
        source = b"""<?php
namespace App\\Command;

use Symfony\\Component\\Console\\Command\\Command;
use Symfony\\Component\\Console\\Attribute\\AsCommand;

#[AsCommand(name: 'app:create-user')]
class CreateUserCommand extends Command
{
    protected function execute($input, $output): int {}
}
"""
        cls_node = _make_node("src/Command/CreateUserCommand.php", 8, NodeKind.CLASS, "CreateUserCommand")
        patterns = self.detector.detect("src/Command/CreateUserCommand.php", None, source, [cls_node], [])
        assert len(patterns) >= 1


class TestSymfonySecurity:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_detect_is_granted(self):
        source = b"""<?php
namespace App\\Controller;

class AdminController extends AbstractController
{
    #[IsGranted('ROLE_ADMIN')]
    public function dashboard(): Response {}
}
"""
        cls_node = _make_node("src/Controller/AdminController.php", 4, NodeKind.CLASS, "AdminController")
        patterns = self.detector.detect("src/Controller/AdminController.php", None, source, [cls_node], [])
        # Should detect security pattern or controller pattern
        assert len(patterns) >= 1

    def test_detect_voter(self):
        source = b"""<?php
namespace App\\Security;

use Symfony\\Component\\Security\\Core\\Authorization\\Voter\\Voter;

class PostVoter extends Voter
{
    protected function supports(string $attribute, mixed $subject): bool {}
    protected function voteOnAttribute(string $attribute, mixed $subject, $token): bool {}
}
"""
        cls_node = _make_node("src/Security/PostVoter.php", 6, NodeKind.CLASS, "PostVoter")
        patterns = self.detector.detect("src/Security/PostVoter.php", None, source, [cls_node], [])
        assert len(patterns) >= 1


class TestSymfonyEmptySource:
    def setup_method(self):
        self.detector = SymfonyDetector()

    def test_empty_php_file(self):
        source = b"<?php\n// empty\n"
        patterns = self.detector.detect("src/test.php", None, source, [], [])
        assert patterns == []


# =====================================================================
# EXPRESS DETECTOR TESTS
# =====================================================================


class TestExpressDetectFramework:
    def setup_method(self):
        self.detector = ExpressDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "express"

    def test_detects_express_in_dependencies(self, tmp_path):
        pkg = {"dependencies": {"express": "^4.18.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_express_in_dev_dependencies(self, tmp_path):
        pkg = {"devDependencies": {"express": "^4.18.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_express_dependency(self, tmp_path):
        pkg = {"dependencies": {"koa": "^2.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_package_json(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_invalid_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not valid json")
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestExpressRouteDetection:
    def setup_method(self):
        self.detector = ExpressDetector()

    def test_detect_basic_routes(self):
        source = b"""const express = require('express');
const app = express();

app.get('/users', (req, res) => {
    res.json([]);
});

app.post('/users', (req, res) => {
    res.json({});
});

app.put('/users/:id', (req, res) => {
    res.json({});
});

app.delete('/users/:id', (req, res) => {
    res.sendStatus(204);
});
"""
        patterns = self.detector.detect("routes/users.js", None, source, [], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) >= 4
        methods = [n.metadata["http_method"] for n in route_nodes]
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods
        assert "DELETE" in methods

    def test_detect_router_routes(self):
        source = b"""const router = require('express').Router();

router.get('/items', handler);
router.post('/items', handler);
"""
        patterns = self.detector.detect("routes/items.js", None, source, [], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) >= 2

    def test_detect_route_with_path(self):
        source = b"""app.get('/api/v1/products', getProducts);
"""
        patterns = self.detector.detect("app.js", None, source, [], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) >= 1
        assert route_nodes[0].metadata["url_pattern"] == "/api/v1/products"

    def test_detect_all_http_methods(self):
        source = b"""app.get('/a', h);
app.post('/b', h);
app.put('/c', h);
app.patch('/d', h);
app.delete('/e', h);
app.options('/f', h);
app.head('/g', h);
app.all('/h', h);
"""
        patterns = self.detector.detect("app.js", None, source, [], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) == 8


class TestExpressMiddleware:
    def setup_method(self):
        self.detector = ExpressDetector()

    def test_detect_middleware(self):
        source = b"""const express = require('express');
const app = express();

app.use('/api', cors());
app.use(express.json());
"""
        patterns = self.detector.detect("app.js", None, source, [], [])
        mw_nodes = _collect_nodes(patterns, NodeKind.MIDDLEWARE)
        assert len(mw_nodes) >= 1


class TestExpressRouterCreation:
    def setup_method(self):
        self.detector = ExpressDetector()

    def test_detect_router_instance(self):
        source = b"""const express = require('express');
const router = express.Router();

router.get('/test', handler);
"""
        func_node = _make_node("routes/test.js", 4, NodeKind.FUNCTION, "handler", language="javascript")
        patterns = self.detector.detect("routes/test.js", None, source, [func_node], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) >= 1


class TestExpressEmptySource:
    def setup_method(self):
        self.detector = ExpressDetector()

    def test_no_routes_returns_empty(self):
        source = b"const x = 1;\n"
        patterns = self.detector.detect("app.js", None, source, [], [])
        route_nodes = _collect_nodes(patterns, NodeKind.ROUTE)
        assert len(route_nodes) == 0


# =====================================================================
# REACT DETECTOR TESTS
# =====================================================================


class TestReactDetectFramework:
    def setup_method(self):
        self.detector = ReactDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "react"

    def test_detects_react_in_dependencies(self, tmp_path):
        pkg = {"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_react_in_dev_dependencies(self, tmp_path):
        pkg = {"devDependencies": {"react": "^18.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_react_dependency(self, tmp_path):
        pkg = {"dependencies": {"vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_package_json(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_invalid_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not valid json")
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestReactComponentDetection:
    def setup_method(self):
        self.detector = ReactDetector()

    def test_detect_function_component(self):
        source = b"""import React from 'react';

function UserCard({ name, email }) {
    return (
        <Card className="wrapper">
            <Header>{name}</Header>
            <Text>{email}</Text>
        </Card>
    );
}

export default UserCard;
"""
        func_node = _make_node(
            "components/UserCard.tsx",
            3,
            NodeKind.FUNCTION,
            "UserCard",
            end_line=11,
            language="typescript",
            source_text='function UserCard({ name, email }) {\n    return (\n        <Card className="wrapper">\n            <Header>{name}</Header>\n            <Text>{email}</Text>\n        </Card>\n    );\n}',
        )
        patterns = self.detector.detect("components/UserCard.tsx", None, source, [func_node], [])
        comp_nodes = _collect_nodes(patterns, NodeKind.COMPONENT)
        assert len(comp_nodes) >= 1
        assert comp_nodes[0].name == "UserCard"
        assert comp_nodes[0].metadata.get("framework") == "react"

    def test_detect_arrow_function_component(self):
        source = b"""const Button = ({ onClick, children }) => {
    return <StyledButton onClick={onClick}>{children}</StyledButton>;
};
"""
        var_node = _make_node(
            "components/Button.tsx",
            1,
            NodeKind.VARIABLE,
            "Button",
            end_line=3,
            language="typescript",
            source_text="const Button = ({ onClick, children }) => {\n    return <StyledButton onClick={onClick}>{children}</StyledButton>;\n};",
        )
        patterns = self.detector.detect("components/Button.tsx", None, source, [var_node], [])
        comp_nodes = _collect_nodes(patterns, NodeKind.COMPONENT)
        assert len(comp_nodes) >= 1


class TestReactHookDetection:
    def setup_method(self):
        self.detector = ReactDetector()

    def test_detect_custom_hook(self):
        source = b"""import { useState, useEffect } from 'react';

function useAuth() {
    const [user, setUser] = useState(null);
    useEffect(() => {
        fetchUser().then(setUser);
    }, []);
    return user;
}
"""
        func_node = _make_node(
            "hooks/useAuth.ts",
            3,
            NodeKind.FUNCTION,
            "useAuth",
            end_line=9,
            language="typescript",
            source_text="function useAuth() {\n    const [user, setUser] = useState(null);\n    useEffect(() => {\n        fetchUser().then(setUser);\n    }, []);\n    return user;\n}",
        )
        patterns = self.detector.detect("hooks/useAuth.ts", None, source, [func_node], [])
        hook_nodes = _collect_nodes(patterns, NodeKind.HOOK)
        assert len(hook_nodes) >= 1
        assert hook_nodes[0].name == "useAuth"

    def test_detect_hook_usage_in_component(self):
        source = b"""function App() {
    const [count, setCount] = useState(0);
    useEffect(() => {}, []);
    return <Counter value={count} />;
}
"""
        func_node = _make_node(
            "App.tsx",
            1,
            NodeKind.FUNCTION,
            "App",
            end_line=5,
            language="typescript",
            source_text="function App() {\n    const [count, setCount] = useState(0);\n    useEffect(() => {}, []);\n    return <Counter value={count} />;\n}",
        )
        patterns = self.detector.detect("App.tsx", None, source, [func_node], [])
        hook_edges = _collect_edges(patterns, EdgeKind.USES_HOOK)
        assert len(hook_edges) >= 1


class TestReactContextDetection:
    def setup_method(self):
        self.detector = ReactDetector()

    def test_detect_create_context(self):
        source = b"""import { createContext, useContext } from 'react';

const ThemeContext = createContext('light');

function ThemeProvider({ children }) {
    return (
        <ThemeContext.Provider value="dark">
            {children}
        </ThemeContext.Provider>
    );
}

function useTheme() {
    return useContext(ThemeContext);
}
"""
        var_node = _make_node(
            "context/theme.tsx", 3, NodeKind.VARIABLE, "ThemeContext", end_line=3, language="typescript"
        )
        func_provider = _make_node(
            "context/theme.tsx",
            5,
            NodeKind.FUNCTION,
            "ThemeProvider",
            end_line=11,
            language="typescript",
            source_text='function ThemeProvider({ children }) {\n    return (\n        <ThemeContext.Provider value="dark">\n            {children}\n        </ThemeContext.Provider>\n    );\n}',
        )
        func_hook = _make_node(
            "context/theme.tsx",
            13,
            NodeKind.FUNCTION,
            "useTheme",
            end_line=15,
            language="typescript",
            source_text="function useTheme() {\n    return useContext(ThemeContext);\n}",
        )
        patterns = self.detector.detect("context/theme.tsx", None, source, [var_node, func_provider, func_hook], [])
        # Should detect context patterns
        all_edges = _collect_edges(patterns)
        context_edges = [
            e for e in all_edges if e.kind in (EdgeKind.PROVIDES_CONTEXT, EdgeKind.CONSUMES_CONTEXT, EdgeKind.USES_HOOK)
        ]
        assert len(context_edges) >= 1


class TestReactNoJSX:
    def setup_method(self):
        self.detector = ReactDetector()

    def test_no_jsx_no_components(self):
        source = b"""function helper(x) {
    return x * 2;
}
"""
        func_node = _make_node(
            "utils/helper.ts",
            1,
            NodeKind.FUNCTION,
            "helper",
            end_line=3,
            language="typescript",
            source_text="function helper(x) {\n    return x * 2;\n}",
        )
        patterns = self.detector.detect("utils/helper.ts", None, source, [func_node], [])
        comp_nodes = _collect_nodes(patterns, NodeKind.COMPONENT)
        assert len(comp_nodes) == 0


# =====================================================================
# TAILWIND DETECTOR TESTS
# =====================================================================


class TestTailwindDetectFramework:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_framework_name(self):
        assert self.detector.framework_name == "tailwind"

    def test_detects_with_config_js(self, tmp_path):
        (tmp_path / "tailwind.config.js").write_text("module.exports = {};")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_config_ts(self, tmp_path):
        (tmp_path / "tailwind.config.ts").write_text("export default {};")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_config_cjs(self, tmp_path):
        (tmp_path / "tailwind.config.cjs").write_text("module.exports = {};")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_config_mjs(self, tmp_path):
        (tmp_path / "tailwind.config.mjs").write_text("export default {};")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_package_json(self, tmp_path):
        pkg = {"dependencies": {"tailwindcss": "^3.4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_with_dev_dependencies(self, tmp_path):
        pkg = {"devDependencies": {"tailwindcss": "^3.4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_v4_css_import(self, tmp_path):
        css_dir = tmp_path / "src"
        css_dir.mkdir()
        (css_dir / "app.css").write_text('@import "tailwindcss";\n')
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_detects_v3_tailwind_directive(self, tmp_path):
        css_dir = tmp_path / "src"
        css_dir.mkdir()
        (css_dir / "styles.css").write_text("@tailwind base;\n@tailwind components;\n@tailwind utilities;\n")
        assert self.detector.detect_framework(str(tmp_path)) is True

    def test_no_tailwind_returns_false(self, tmp_path):
        pkg = {"dependencies": {"bootstrap": "^5.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_no_files_returns_false(self, tmp_path):
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_invalid_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("not valid json")
        assert self.detector.detect_framework(str(tmp_path)) is False

    def test_skips_node_modules(self, tmp_path):
        """CSS files in node_modules should be ignored."""
        nm = tmp_path / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "styles.css").write_text('@import "tailwindcss";\n')
        assert self.detector.detect_framework(str(tmp_path)) is False


class TestTailwindThemeDetection:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_detect_v4_theme_block(self):
        source = b"""@import "tailwindcss";

@theme {
    --color-primary: #3b82f6;
    --color-secondary: #10b981;
    --font-sans: 'Inter', sans-serif;
}
"""
        patterns = self.detector.detect("app.css", None, source, [], [])
        theme_nodes = _collect_nodes(patterns, NodeKind.TAILWIND_THEME_TOKEN)
        assert len(theme_nodes) >= 1


class TestTailwindUtilityDetection:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_detect_custom_utility(self):
        source = b"""@utility content-auto {
    content-visibility: auto;
}

@utility scrollbar-hidden {
    scrollbar-width: none;
}
"""
        patterns = self.detector.detect("utilities.css", None, source, [], [])
        utility_nodes = _collect_nodes(patterns, NodeKind.TAILWIND_UTILITY)
        assert len(utility_nodes) >= 2


class TestTailwindApplyDetection:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_detect_apply_directive(self):
        source = b""".btn {
    @apply px-4 py-2 bg-blue-500 text-white rounded;
}

.card {
    @apply p-6 shadow-lg rounded-xl;
}
"""
        css_node = _make_node("styles.css", 1, NodeKind.CSS_CLASS, "btn", end_line=3, language="css")
        css_node2 = _make_node("styles.css", 5, NodeKind.CSS_CLASS, "card", end_line=7, language="css")
        patterns = self.detector.detect("styles.css", None, source, [css_node, css_node2], [])
        apply_edges = _collect_edges(patterns, EdgeKind.TAILWIND_APPLIES)
        assert len(apply_edges) >= 2


class TestTailwindSourceDirective:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_detect_source_directive(self):
        source = b"""@import "tailwindcss";
@source "../src/**/*.{html,js,ts,jsx,tsx}";
"""
        patterns = self.detector.detect("app.css", None, source, [], [])
        # Should detect source directive
        all_nodes = _collect_nodes(patterns)
        all_edges = _collect_edges(patterns)
        assert len(all_nodes) + len(all_edges) >= 1


class TestTailwindEmptySource:
    def setup_method(self):
        self.detector = TailwindDetector()

    def test_plain_css_no_tailwind(self):
        source = b".btn { color: red; }\n"
        patterns = self.detector.detect("styles.css", None, source, [], [])
        assert patterns == []

    def test_empty_css(self):
        source = b"/* empty */\n"
        patterns = self.detector.detect("styles.css", None, source, [], [])
        assert patterns == []
