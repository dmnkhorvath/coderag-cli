import os
import pytest
from unittest.mock import MagicMock, patch
from coderag.core.models import Node, Edge, NodeKind, EdgeKind
from coderag.plugins.php.frameworks.laravel import LaravelDetector

@pytest.fixture
def detector():
    return LaravelDetector()

def test_detect_model_with_target_node(detector):
    cls_node = Node(
        id="cls1", kind=NodeKind.CLASS, name="User", qualified_name="App\\Models\\User",
        file_path="app/Models/User.php", start_line=10, end_line=20, language="php"
    )
    base_node = Node(
        id="model_base", kind=NodeKind.CLASS, name="Model", qualified_name="Illuminate\\Database\\Eloquent\\Model",
        file_path="vendor/laravel/framework/src/Illuminate/Database/Eloquent/Model.php", start_line=1, end_line=10, language="php"
    )
    extends_edge = Edge(source_id="cls1", target_id="model_base", kind=EdgeKind.EXTENDS)
    
    source = b"class User extends Model {}"
    
    patterns = detector.detect("app/Models/User.php", None, source, [cls_node, base_node], [extends_edge])
    assert len(patterns) == 1
    assert patterns[0].pattern_type == "model"

def test_infer_project_root_not_found(detector):
    store = MagicMock()
    store.find_nodes.return_value = [
        Node(id="f1", kind=NodeKind.FILE, name="User.php", qualified_name="User.php", file_path="/var/www/app/Models/User.php", start_line=1, end_line=10, language="php")
    ]
    
    with patch("os.path.isfile", return_value=False):
        root = detector._infer_project_root(store)
        assert root is None

def test_extract_routes_missing_file(detector, tmp_path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    web_php = routes_dir / "web.php"
    web_php.write_text("Route::get('/', 'HomeController@index');")
    
    store = MagicMock()
    store.find_nodes.return_value = []
    
    pattern = detector._extract_routes(store, str(tmp_path))
    assert pattern is not None

def test_extract_routes_middleware_list(detector, tmp_path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    web_php = routes_dir / "web.php"
    web_php.write_text("Route::get('/admin', 'AdminController@index')->middleware(['auth', 'admin']);")
    
    store = MagicMock()
    store.find_nodes.return_value = []
    
    pattern = detector._extract_routes(store, str(tmp_path))
    assert pattern is not None
    assert len(pattern.nodes) == 1
    assert pattern.nodes[0].metadata["middleware"] == ["auth", "admin"]

def test_resolve_controller_not_found(detector):
    store = MagicMock()
    store.find_nodes.return_value = []
    assert detector._resolve_controller("MissingController", store) is None

def test_extract_event_listener_mappings_no_file(detector, tmp_path):
    store = MagicMock()
    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is None

def test_extract_event_listener_mappings_fallback_to_class(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("""
    protected $listen = [
        MyEvent::class => [
            MyListener::class,
        ]
    ];
    """)
    
    store = MagicMock()
    def mock_find_nodes(kind, name_pattern, limit):
        if name_pattern == "MyEvent":
            return [Node(id="evt1", kind=NodeKind.EVENT, name="MyEvent", qualified_name="MyEvent", file_path="test.php", start_line=1, end_line=10, language="php")]
        if name_pattern == "MyListener":
            if kind == NodeKind.LISTENER:
                return []
            if kind == NodeKind.CLASS:
                return [Node(id="cls1", kind=NodeKind.CLASS, name="MyListener", qualified_name="MyListener", file_path="test.php", start_line=1, end_line=10, language="php")]
        return []
        
    store.find_nodes.side_effect = mock_find_nodes
    
    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is not None
    assert len(pattern.edges) == 2
    assert pattern.edges[0].metadata["listener"] == "MyListener"

def test_extract_event_listener_mappings_listener_not_found(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("""
    protected $listen = [
        MyEvent::class => [
            MissingListener::class,
        ]
    ];
    """)
    
    store = MagicMock()
    def mock_find_nodes(kind, name_pattern, limit):
        if name_pattern == "MyEvent":
            return [Node(id="evt1", kind=NodeKind.EVENT, name="MyEvent", qualified_name="MyEvent", file_path="test.php", start_line=1, end_line=10, language="php")]
        return []
        
    store.find_nodes.side_effect = mock_find_nodes
    
    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is None
