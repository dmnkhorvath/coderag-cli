import json
from unittest.mock import MagicMock, patch

import pytest

from coderag.enrichment.phpstan import PHPStanEnricher, PHPStanResult
from coderag.storage.sqlite_store import SQLiteStore


@pytest.fixture
def enricher():
    return PHPStanEnricher("/fake/root")


def test_is_available_local(enricher):
    with patch("subprocess.run") as mock_run:

        def mock_run_side_effect(*args, **kwargs):
            if "vendor" in args[0][0]:
                return MagicMock(returncode=0, stdout="PHPStan 1.10.0")
            raise FileNotFoundError()

        mock_run.side_effect = mock_run_side_effect
        assert enricher.is_available() is True
        assert enricher.phpstan_path.endswith("phpstan")


def test_analyze_success(enricher):
    mock_output = {
        "files": {
            "/fake/root/src/User.php": {
                "messages": [
                    {
                        "message": "Method User::getName() should return string but returns int.",
                        "line": 15,
                        "identifier": "return.type",
                        "tip": "Add return type",
                    }
                ]
            }
        }
    }
    with patch("subprocess.run") as mock_run, patch.object(enricher, "is_available", return_value=True):
        mock_run.return_value = MagicMock(stdout=json.dumps(mock_output), returncode=1)
        results = enricher.analyze(["/fake/root/src/User.php"])
        assert len(results) == 1
        assert "src/User.php" in results
        assert results["src/User.php"][0].file_path == "src/User.php"


def test_analyze_file_not_found(enricher):
    with patch("subprocess.run") as mock_run, patch.object(enricher, "is_available", return_value=True):
        mock_run.side_effect = FileNotFoundError()
        results = enricher.analyze()
        assert results == {}


def test_analyze_empty_output(enricher):
    with patch("subprocess.run") as mock_run, patch.object(enricher, "is_available", return_value=True):
        mock_run.return_value = MagicMock(stdout="  ", returncode=0)
        results = enricher.analyze()
        assert results == {}


def test_analyze_invalid_json(enricher):
    with patch("subprocess.run") as mock_run, patch.object(enricher, "is_available", return_value=True):
        mock_run.return_value = MagicMock(stdout="invalid json", returncode=1)
        results = enricher.analyze()
        assert results == {}


def test_enrich_nodes_success(enricher):
    with patch.object(enricher, "is_available", return_value=True), patch.object(enricher, "analyze") as mock_analyze:
        mock_analyze.return_value = {
            "src/User.php": [PHPStanResult(file_path="src/User.php", line=15, message="Error")]
        }

        store_mock = MagicMock(spec=SQLiteStore)
        report = enricher.enrich_nodes(store_mock, ["/fake/root/src/User.php"])

        assert report.files_analyzed == 1
        assert report.errors_found == 1


def test_enrich_nodes_no_results(enricher):
    with patch.object(enricher, "is_available", return_value=True), patch.object(enricher, "analyze", return_value={}):
        store_mock = MagicMock(spec=SQLiteStore)
        report = enricher.enrich_nodes(store_mock)

        assert report.files_analyzed == 0
        assert report.errors_found == 0
