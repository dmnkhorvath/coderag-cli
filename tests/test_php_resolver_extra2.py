from coderag.plugins.php.resolver import PHPResolver


def test_php_resolver_qname_index(tmp_path):
    resolver = PHPResolver()
    resolver.set_project_root(str(tmp_path))
    resolver._qname_index["App\\Models\\User"] = str(tmp_path / "app/Models/User.php")
    result = resolver.resolve("App\\Models\\User", str(tmp_path / "test.php"))
    assert result.resolved_path == str(tmp_path / "app/Models/User.php")
    assert result.resolution_strategy == "qname_index"


def test_php_resolver_psr4_exact_match(tmp_path):
    resolver = PHPResolver()
    resolver.set_project_root(str(tmp_path))
    resolver._psr4_map = {"App\\": ["app/"]}

    app_dir = tmp_path / "app" / "Models"
    app_dir.mkdir(parents=True)
    (app_dir / "User.php").touch()

    result = resolver._resolve_psr4("App\\Models\\User")
    assert result == str(tmp_path / "app/Models/User.php")
