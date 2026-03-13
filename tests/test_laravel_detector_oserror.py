from unittest.mock import patch

from coderag.core.models import Node, NodeKind
from coderag.plugins.php.frameworks.laravel import LaravelDetector


class MockStore:
    def __init__(self, path):
        self.path = path

    def find_nodes(self, **kwargs):
        return [
            Node(
                id="f1",
                kind=NodeKind.FILE,
                name="artisan",
                qualified_name="artisan",
                file_path=str(self.path / "artisan"),
                start_line=1,
                end_line=1,
                language="php",
            )
        ]


def test_laravel_route_file_read_error(tmp_path):
    detector = LaravelDetector()
    routes_dir = tmp_path / "routes"
    routes_dir.mkdir()
    (routes_dir / "api.php").touch()

    with patch("builtins.open", side_effect=OSError("Permission denied")):
        patterns = detector.detect_global_patterns(MockStore(tmp_path))
        assert patterns == []
