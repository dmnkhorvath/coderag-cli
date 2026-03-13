from unittest.mock import MagicMock, patch

import pytest

from coderag.core.models import Node, NodeKind
from coderag.plugins.php.frameworks.laravel import LaravelDetector


@pytest.fixture
def detector():
    return LaravelDetector()


def test_detect_framework_oserror(detector, tmp_path):
    (tmp_path / "artisan").touch()
    composer = tmp_path / "composer.json"
    composer.write_text("{}")
    with patch("builtins.open", side_effect=OSError):
        assert detector.detect_framework(str(tmp_path)) is True


def test_detect_global_patterns_no_root(detector):
    store = MagicMock()
    with patch.object(detector, "_infer_project_root", return_value=None):
        patterns = detector.detect_global_patterns(store)
        assert patterns == []


def test_extract_routes_empty(detector, tmp_path):
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    web_php = routes_dir / "web.php"
    web_php.write_text("<?php\n// no routes here")

    store = MagicMock()
    pattern = detector._extract_routes(store, str(tmp_path))
    assert pattern is None


def test_extract_event_listener_mappings_empty(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("<?php\n// no listeners here")

    store = MagicMock()
    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is None


def test_extract_event_listener_mappings_missing_nodes(detector, tmp_path):
    app_dir = tmp_path / "app" / "Providers"
    app_dir.mkdir(parents=True)
    esp = app_dir / "EventServiceProvider.php"
    esp.write_text("""
    protected $listen = [
        MissingEvent::class => [
            MissingListener::class,
        ],
        FoundEvent::class => [
            MissingListener2::class,
        ]
    ];
    """)

    store = MagicMock()

    def mock_find_nodes(kind, name_pattern, limit):
        if name_pattern == "FoundEvent":
            return [
                Node(
                    id="evt1",
                    kind=NodeKind.EVENT,
                    name="FoundEvent",
                    qualified_name="FoundEvent",
                    file_path="test.php",
                    start_line=1,
                    end_line=10,
                    language="php",
                )
            ]
        return []

    store.find_nodes.side_effect = mock_find_nodes

    pattern = detector._extract_event_listener_mappings(store, str(tmp_path))
    assert pattern is None


def test_resolve_controller_branches(detector):
    store = MagicMock()

    # Test ::class with method
    store.find_nodes.return_value = [
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="index",
            qualified_name="index",
            file_path="UserController.php",
            start_line=1,
            end_line=10,
            language="php",
        )
    ]
    assert detector._resolve_controller("UserController::class, 'index'", store) == "m1"

    # Test @ method
    assert detector._resolve_controller("UserController@index", store) == "m1"

    # Test just class
    store.find_nodes.return_value = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="UserController",
            qualified_name="UserController",
            file_path="UserController.php",
            start_line=1,
            end_line=10,
            language="php",
        )
    ]
    assert detector._resolve_controller("UserController", store) == "c1"

    # Test empty
    assert detector._resolve_controller("", store) is None
