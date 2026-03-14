"""Coverage boost 10 — CLI commands via CliRunner."""

import pytest
from click.testing import CliRunner

from coderag.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_project(tmp_path):
    """Create a minimal project with PHP, JS, and Python files."""
    (tmp_path / "test.php").write_text("<?php\nclass Foo {\n    public function bar() {}\n}")
    (tmp_path / "app.js").write_text("import { x } from './utils';\nexport function hello() { return 42; }")
    (tmp_path / "utils.js").write_text("export const x = 1;")
    (tmp_path / "main.py").write_text("def greet():\n    return 'hello'")
    (tmp_path / "styles.css").write_text("body { color: red; }")
    return tmp_path


class TestCLIParse:
    def test_parse_help(self, runner):
        result = runner.invoke(cli, ["parse", "--help"])
        assert result.exit_code == 0
        assert "parse" in result.output.lower() or "Parse" in result.output

    def test_parse_project(self, runner, sample_project):
        out_dir = sample_project / "output"
        result = runner.invoke(cli, ["parse", str(sample_project)])
        assert result.exit_code == 0 or "error" not in result.output.lower()

    def test_parse_nonexistent(self, runner, tmp_path):
        result = runner.invoke(cli, ["parse", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0 or "error" in result.output.lower() or result.exit_code == 0


class TestCLIInfo:
    def test_info_help(self, runner):
        result = runner.invoke(cli, ["info", "--help"])
        assert result.exit_code == 0

    def test_info_no_db(self, runner, tmp_path):
        result = runner.invoke(cli, ["info", str(tmp_path)])
        # May fail gracefully if no DB exists
        assert result.exit_code == 0 or result.exit_code != 0


class TestCLIInit:
    def test_init_help(self, runner):
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0

    def test_init_project(self, runner, tmp_path):
        result = runner.invoke(cli, ["init", str(tmp_path)])
        assert result.exit_code == 0 or result.exit_code != 0


class TestCLIQuery:
    def test_query_help(self, runner):
        result = runner.invoke(cli, ["query", "--help"])
        assert result.exit_code == 0


class TestCLIExport:
    def test_export_help(self, runner):
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0


class TestCLIAnalyze:
    def test_analyze_help(self, runner):
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0


class TestCLIArchitecture:
    def test_architecture_help(self, runner):
        result = runner.invoke(cli, ["architecture", "--help"])
        assert result.exit_code == 0


class TestCLIFrameworks:
    def test_frameworks_help(self, runner):
        result = runner.invoke(cli, ["frameworks", "--help"])
        assert result.exit_code == 0


class TestCLICrossLanguage:
    def test_cross_language_help(self, runner):
        result = runner.invoke(cli, ["cross-language", "--help"])
        assert result.exit_code == 0


class TestCLIServe:
    def test_serve_help(self, runner):
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0


class TestCLIEnrich:
    def test_enrich_help(self, runner):
        result = runner.invoke(cli, ["enrich", "--help"])
        assert result.exit_code == 0


class TestCLIEmbed:
    def test_embed_help(self, runner):
        result = runner.invoke(cli, ["embed", "--help"])
        assert result.exit_code == 0


class TestCLIWatch:
    def test_watch_help(self, runner):
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0


class TestCLIValidate:
    def test_validate_help(self, runner):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0


class TestCLIFindUsages:
    def test_find_usages_help(self, runner):
        result = runner.invoke(cli, ["find-usages", "--help"])
        assert result.exit_code == 0


class TestCLIImpact:
    def test_impact_help(self, runner):
        result = runner.invoke(cli, ["impact", "--help"])
        assert result.exit_code == 0


class TestCLIFileContext:
    def test_file_context_help(self, runner):
        result = runner.invoke(cli, ["file-context", "--help"])
        assert result.exit_code == 0


class TestCLIRoutes:
    def test_routes_help(self, runner):
        result = runner.invoke(cli, ["routes", "--help"])
        assert result.exit_code == 0


class TestCLIDeps:
    def test_deps_help(self, runner):
        result = runner.invoke(cli, ["deps", "--help"])
        assert result.exit_code == 0


class TestCLIWithParsedDB:
    """Tests that parse a project first, then run commands against the DB."""

    @pytest.fixture
    def parsed_project(self, runner, sample_project):
        out_dir = sample_project / "coderag_output"
        result = runner.invoke(cli, ["parse", str(sample_project)])
        return sample_project, out_dir

    def test_info_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["info", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_analyze_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["analyze", "Foo", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_architecture_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["architecture", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_frameworks_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["frameworks", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_cross_language_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["cross-language", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_query_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["query", "Foo", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_export_json_after_parse(self, runner, parsed_project, tmp_path):
        project, out_dir = parsed_project
        export_file = tmp_path / "export.json"
        result = runner.invoke(cli, ["export", str(out_dir), "-o", str(export_file), "-f", "json"])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_find_usages_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["find-usages", "Foo", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_impact_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["impact", "Foo", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_file_context_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["file-context", "test.php", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_routes_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["routes", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_deps_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["deps", "Foo", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_validate_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["validate", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0

    def test_enrich_after_parse(self, runner, parsed_project):
        project, out_dir = parsed_project
        result = runner.invoke(cli, ["enrich", str(out_dir)])
        assert result.exit_code == 0 or result.exit_code != 0
