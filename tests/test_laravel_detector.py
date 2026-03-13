import json
from unittest.mock import MagicMock, patch

import pytest

from coderag.core.models import Edge, EdgeKind, Node, NodeKind
from coderag.plugins.php.frameworks.laravel import LaravelDetector


@pytest.fixture
def detector():
    return LaravelDetector()


def test_framework_name(detector):
    assert detector.framework_name == "laravel"


def test_detect_framework_with_artisan(detector, tmp_path):
    (tmp_path / "artisan").touch()
    assert detector.detect_framework(str(tmp_path)) is True


def test_detect_framework_with_composer(detector, tmp_path):
    (tmp_path / "artisan").touch()
    composer = tmp_path / "composer.json"
    composer.write_text(json.dumps({"require": {"laravel/framework": "^10.0"}}))
    assert detector.detect_framework(str(tmp_path)) is True


def test_detect_framework_composer_invalid_json(detector, tmp_path):
    (tmp_path / "artisan").touch()
    composer = tmp_path / "composer.json"
    composer.write_text("{invalid json}")
    assert detector.detect_framework(str(tmp_path)) is True


def test_detect_framework_false(detector, tmp_path):
    assert detector.detect_framework(str(tmp_path)) is False


def test_detect_model(detector):
    cls_node = Node(
        id="cls1",
        kind=NodeKind.CLASS,
        name="User",
        qualified_name="App\\Models\\User",
        file_path="app/Models/User.php",
        start_line=10,
        end_line=20,
        language="php",
    )
    extends_edge = Edge(
        source_id="cls1", target_id="model_base", kind=EdgeKind.EXTENDS, metadata={"target_name": "Model"}
    )

    source = b"""
    class User extends Model {
        public function posts() {
            return $this->hasMany(Post::class);
        }
        public function profile() {
            return $this->hasOne('Profile');
        }
    }
    """

    patterns = detector.detect("app/Models/User.php", None, source, [cls_node], [extends_edge])
    assert len(patterns) == 1
    assert patterns[0].pattern_type == "model"
    assert len(patterns[0].nodes) == 1
    assert patterns[0].nodes[0].kind == NodeKind.MODEL
    assert len(patterns[0].edges) == 2

    has_many = next(e for e in patterns[0].edges if e.metadata["relationship_type"] == "hasMany")
    assert has_many.metadata["related_model"] == "Post"

    has_one = next(e for e in patterns[0].edges if e.metadata["relationship_type"] == "hasOne")
    assert has_one.metadata["related_model"] == "Profile"


def test_detect_other_classes(detector):
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="UserEvent",
            qualified_name="App\\Events\\UserEvent",
            file_path="app/Events/UserEvent.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="c2",
            kind=NodeKind.CLASS,
            name="UserListener",
            qualified_name="App\\Listeners\\UserListener",
            file_path="app/Listeners/UserListener.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="c3",
            kind=NodeKind.CLASS,
            name="AuthMiddleware",
            qualified_name="App\\Http\\Middleware\\AuthMiddleware",
            file_path="app/Http/Middleware/AuthMiddleware.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="c4",
            kind=NodeKind.CLASS,
            name="AppServiceProvider",
            qualified_name="App\\Providers\\AppServiceProvider",
            file_path="app/Providers/AppServiceProvider.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="c5",
            kind=NodeKind.CLASS,
            name="UserController",
            qualified_name="App\\Http\\Controllers\\UserController",
            file_path="app/Http/Controllers/UserController.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
    ]

    edges = [
        Edge(source_id="c1", target_id="missing", kind=EdgeKind.EXTENDS, metadata={"target_name": "Event"}),
        Edge(source_id="c2", target_id="missing", kind=EdgeKind.EXTENDS, metadata={"target_name": "Listener"}),
        Edge(source_id="c3", target_id="missing", kind=EdgeKind.EXTENDS, metadata={"target_name": "Middleware"}),
        Edge(source_id="c4", target_id="missing", kind=EdgeKind.EXTENDS, metadata={"target_name": "ServiceProvider"}),
        Edge(source_id="c5", target_id="missing", kind=EdgeKind.EXTENDS, metadata={"target_name": "Controller"}),
    ]

    patterns = detector.detect("test.php", None, b"", nodes, edges)
    assert len(patterns) == 5
    types = {p.pattern_type for p in patterns}
    assert types == {"event", "listener", "middleware", "provider", "controller"}


def test_infer_project_root(detector):
    store = MagicMock()
    store.find_nodes.return_value = [
        Node(
            id="f1",
            kind=NodeKind.FILE,
            name="User.php",
            qualified_name="User.php",
            file_path="/var/www/app/Models/User.php",
            start_line=1,
            end_line=10,
            language="php",
        )
    ]

    with patch("os.path.isfile") as mock_isfile:

        def side_effect(path):
            return path == "/var/www/artisan"

        mock_isfile.side_effect = side_effect

        root = detector._infer_project_root(store)
        assert root == "/var/www"


def test_infer_project_root_no_nodes(detector):
    store = MagicMock()
    store.find_nodes.return_value = []
    assert detector._infer_project_root(store) is None


def test_extract_routes(detector, tmp_path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    web_php = routes_dir / "web.php"
    web_php.write_text("""
    Route::get('/users', [UserController::class, 'index'])->name('users.index')->middleware('auth');
    Route::post('/users', 'UserController@store');
    Route::resource('posts', PostController::class);
    """)

    api_php = routes_dir / "api.php"
    api_php.write_text("""
    Route::get('/status', 'ApiController@status');
    """)

    store = MagicMock()
    store.find_nodes.side_effect = lambda kind, name_pattern=None, limit=None: [
        Node(
            id="ctrl1",
            kind=NodeKind.CLASS,
            name="UserController",
            qualified_name="UserController",
            file_path="UserController.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="ctrl2",
            kind=NodeKind.CLASS,
            name="PostController",
            qualified_name="PostController",
            file_path="PostController.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
        Node(
            id="ctrl3",
            kind=NodeKind.CLASS,
            name="ApiController",
            qualified_name="ApiController",
            file_path="ApiController.php",
            start_line=1,
            end_line=10,
            language="php",
        ),
    ]

    pattern = detector._extract_routes(store, str(tmp_path))
    assert pattern is not None
    assert pattern.pattern_type == "routes"

    # get, post, 7 resource routes, 1 api route = 10 routes
    assert len(pattern.nodes) == 10

    get_route = next(
        n for n in pattern.nodes if n.metadata.get("http_method") == "GET" and n.metadata.get("url_pattern") == "/users"
    )
    assert get_route.metadata["route_name"] == "users.index"
    assert get_route.metadata["middleware"] == ["auth"]
    assert get_route.metadata["controller_ref"] == "UserController::class, 'index'"

    api_route = next(
        n
        for n in pattern.nodes
        if n.metadata.get("http_method") == "GET" and n.metadata.get("url_pattern") == "/api/status"
    )
    assert api_route is not None

    assert len(pattern.edges) > 0


def test_extract_routes_oserror(detector, tmp_path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    web_php = routes_dir / "web.php"
    web_php.write_text("Route::get('/users', 'UserController@index');")

    store = MagicMock()
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        pattern = detector._extract_routes(store, str(tmp_path))
        assert pattern is None


def test_extract_event_listener_mappings(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("""
    protected $listen = [
        Registered::class => [
            SendEmailVerificationNotification::class,
        ],
        MissingEvent::class => [
            MissingListener::class,
        ]
    ];
    """)

    store = MagicMock()

    def mock_find_nodes(kind, name_pattern, limit):
        if name_pattern == "Registered" and kind == NodeKind.EVENT:
            return [
                Node(
                    id="evt1",
                    kind=NodeKind.EVENT,
                    name="Registered",
                    qualified_name="Registered",
                    file_path="test.php",
                    start_line=1,
                    end_line=10,
                    language="php",
                )
            ]
        if name_pattern == "SendEmailVerificationNotification" and kind == NodeKind.LISTENER:
            return [
                Node(
                    id="lst1",
                    kind=NodeKind.LISTENER,
                    name="SendEmailVerificationNotification",
                    qualified_name="SendEmailVerificationNotification",
                    file_path="test.php",
                    start_line=1,
                    end_line=10,
                    language="php",
                )
            ]
        return []

    store.find_nodes.side_effect = mock_find_nodes

    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is not None
    assert pattern.pattern_type == "event_listeners"
    assert len(pattern.edges) == 2  # One DISPATCHES_EVENT, one LISTENS_TO

    assert pattern.edges[0].kind == EdgeKind.DISPATCHES_EVENT
    assert pattern.edges[0].metadata["event"] == "Registered"
    assert pattern.edges[0].metadata["listener"] == "SendEmailVerificationNotification"


def test_extract_event_listener_mappings_oserror(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("TestEvent::class => [TestListener::class]")

    store = MagicMock()
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
        assert pattern is None


def test_detect_global_patterns(detector, tmp_path):
    # Setup routes
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    (routes_dir / "web.php").write_text("Route::get('/test', 'TestController@index');")

    # Setup EventServiceProvider
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    (app_dir / "EventServiceProvider.php").write_text("TestEvent::class => [TestListener::class]")

    store = MagicMock()
    store.find_nodes.side_effect = lambda kind, name_pattern=None, limit=None: (
        [
            Node(
                id="f1",
                kind=NodeKind.FILE,
                name="artisan",
                qualified_name="artisan",
                file_path=str(tmp_path / "artisan"),
                start_line=1,
                end_line=10,
                language="php",
            )
        ]
        if kind == NodeKind.FILE
        else [
            Node(
                id=f"n_{name_pattern}",
                kind=kind,
                name=name_pattern or "test",
                qualified_name=name_pattern or "test",
                file_path="test.php",
                start_line=1,
                end_line=10,
                language="php",
            )
        ]
    )

    with patch.object(detector, "_infer_project_root", return_value=str(tmp_path)):
        patterns = detector.detect_global_patterns(store)
        assert len(patterns) == 2
        types = {p.pattern_type for p in patterns}
        assert types == {"routes", "event_listeners"}
