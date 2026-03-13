from unittest.mock import MagicMock, patch

from coderag.plugins.php.extractor import PHPExtractor, _child_by_field


def test_extract_parse_exception():
    extractor = PHPExtractor()
    # Replace the parser instance with a mock that raises an exception
    mock_parser = MagicMock()
    mock_parser.parse.side_effect = Exception("Parse boom")
    extractor._parser = mock_parser

    result = extractor.extract("test.php", b"<?php echo 1;")
    assert len(result.errors) == 1
    assert "Parse boom" in result.errors[0].message


def test_dispatch_declaration_exception():
    extractor = PHPExtractor()
    source = b"<?php class Foo {}"
    with patch.object(extractor, "_handle_class", side_effect=Exception("Handler boom")):
        result = extractor.extract("test.php", source)
        assert len(result.errors) == 1
        assert "Handler boom" in result.errors[0].message


@patch("coderag.plugins.php.extractor._child_by_field")
def test_extract_parameters_fallback(mock_child_by_field):
    original = _child_by_field

    def side_effect(node, field_name):
        if field_name == "parameters":
            return None
        return original(node, field_name)

    mock_child_by_field.side_effect = side_effect

    extractor = PHPExtractor()
    source = b"<?php function foo($a, $b) {}"
    result = extractor.extract("test.php", source)

    func_nodes = [n for n in result.nodes if n.kind.value == "function"]
    assert len(func_nodes) == 1
    assert len(func_nodes[0].metadata.get("parameters", [])) == 2


@patch("coderag.plugins.php.extractor._child_by_field")
def test_handle_const_fallback_name(mock_child_by_field):
    original = _child_by_field

    def side_effect(node, field_name):
        if field_name == "name" and node.type == "const_element":
            return None
        return original(node, field_name)

    mock_child_by_field.side_effect = side_effect

    extractor = PHPExtractor()
    source = b"<?php const FOO = 1;"
    result = extractor.extract("test.php", source)

    const_nodes = [n for n in result.nodes if n.kind.value == "constant"]
    assert len(const_nodes) == 1
    assert const_nodes[0].name == "FOO"
