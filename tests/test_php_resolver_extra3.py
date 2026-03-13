from unittest.mock import patch

from coderag.plugins.php.resolver import PHPResolver


def test_resolve_psr4_exact_match():
    resolver = PHPResolver()
    resolver._psr4_map = {"App\\": ["app/"]}

    with patch("os.path.isfile", return_value=True):
        result = resolver._resolve_psr4("App\\User")
        assert result is not None
        assert result.endswith("app/User.php")
