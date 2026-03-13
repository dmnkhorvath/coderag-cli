from unittest.mock import MagicMock, patch

from coderag.enrichment.phpstan import PHPStanEnricher, PHPStanResult, _extract_type_from_message


def test_extract_deprecated_class():
    message = "Method Foo::bar() has typehint with deprecated class Baz."
    info = _extract_type_from_message(message)
    assert info.get("deprecated_type") is True


@patch("subprocess.run")
def test_is_available_no_phpstan_in_version(mock_run):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Some Other Tool 1.0.0"
    mock_run.return_value = mock_result

    enricher = PHPStanEnricher("/tmp")
    assert enricher.is_available() is True
    assert enricher._version == "Some Other Tool 1.0.0"


@patch("subprocess.run")
def test_get_version_calls_is_available(mock_run):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "PHPStan 1.10.0"
    mock_run.return_value = mock_result

    enricher = PHPStanEnricher("/tmp")
    version = enricher.get_version()
    assert version == "1.10.0"


@patch("subprocess.run")
@patch.object(PHPStanEnricher, "is_available", return_value=True)
def test_analyze_exit_code_greater_than_1(mock_is_available, mock_run):
    mock_result = MagicMock()
    mock_result.returncode = 2
    mock_result.stdout = ""
    mock_result.stderr = "Fatal error"
    mock_run.return_value = mock_result

    enricher = PHPStanEnricher("/tmp")
    enricher._phpstan_path = "phpstan"
    results = enricher.analyze(["test.php"])
    assert results == {}


def test_parse_json_output_invalid_json_after_brace():
    enricher = PHPStanEnricher("/tmp")
    output = "Some text before { invalid json"
    results = enricher._parse_json_output(output)
    assert results == {}


@patch.object(PHPStanEnricher, "is_available", return_value=True)
def test_enrich_nodes_fallback_to_rel_path(mock_is_available):
    enricher = PHPStanEnricher("/tmp")

    mock_store = MagicMock()
    mock_store.find_nodes.side_effect = [[], []]

    with patch.object(enricher, "analyze") as mock_analyze:
        mock_analyze.return_value = {
            "src/test.php": [PHPStanResult(file_path="src/test.php", line=10, message="Error")]
        }

        report = enricher.enrich_nodes(mock_store)

        assert report.files_analyzed == 1
        assert report.nodes_enriched == 0
        assert mock_store.find_nodes.call_count == 2
