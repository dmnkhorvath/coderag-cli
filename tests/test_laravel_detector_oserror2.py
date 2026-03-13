from unittest.mock import patch

from coderag.plugins.php.frameworks.laravel import LaravelDetector


@patch("os.path.isdir", return_value=True)
@patch("os.listdir", return_value=["api.php"])
@patch("os.path.isfile", return_value=True)
def test_laravel_route_file_oserror(mock_isfile, mock_listdir, mock_isdir):
    detector = LaravelDetector()
    with patch("builtins.open", side_effect=OSError("Permission denied")):
        patterns = detector.detect("app/Http/Controllers/Test.php", None, b"", [], [])
        # Should handle OSError gracefully and return empty patterns for routes
        assert isinstance(patterns, list)
