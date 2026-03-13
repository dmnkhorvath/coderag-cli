import pytest

from coderag.core.models import Node, NodeKind
from coderag.plugins.php.frameworks.symfony import SymfonyDetector


@pytest.fixture
def detector():
    return SymfonyDetector()


def test_framework_name(detector):
    assert detector.framework_name == "symfony"


def test_detect_global_patterns(detector):
    assert detector.detect_global_patterns("/tmp") == []


def test_detect_empty_source(detector):
    assert detector.detect("test.php", None, b"", [], []) == []


def test_find_enclosing_class_continue(detector):
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="C1",
            qualified_name="C1",
            file_path="test.php",
            start_line=10,
            end_line=20,
            language="php",
        )
    ]
    assert detector._find_enclosing_class(5, nodes) is None


def test_find_method_after_line_regex_none(detector):
    assert detector._find_method_after_line_regex(1, "<?php\n// no method", "test.php") == (None, None)


def test_detect_dependency_injection_autowire(detector):
    source = b"""<?php
class MyService {
    public function __construct(
        #[Autowire(service: 'some.service')]
        private $service
    ) {}
}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_dependency_injection_tagged_iterator(detector):
    source = b"""<?php
class MyService {
    public function __construct(
        #[TaggedIterator('app.handler')]
        private iterable $handlers
    ) {}
}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_template_references_with_method_node(detector):
    source = b"""<?php
class MyController {
    #[Template('users/list.html.twig')]
    public function list() {}
}"""
    nodes = [
        Node(
            id="m1",
            kind=NodeKind.METHOD,
            name="list",
            qualified_name="MyController::list",
            file_path="test.php",
            start_line=4,
            end_line=4,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_events_with_class_node(detector):
    source = b"""<?php
class MyListener {
    #[AsEventListener(event: 'kernel.request')]
    public function onKernelRequest() {}
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyListener",
            qualified_name="MyListener",
            file_path="test.php",
            start_line=2,
            end_line=5,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_detect_commands_no_class(detector):
    source = b"""<?php
#[AsCommand(name: 'app:create-user')]
// no class
"""
    detector.detect("test.php", None, source, [], [])


def test_detect_security_with_class_node(detector):
    source = b"""<?php
class MyController {
    #[IsGranted('ROLE_ADMIN')]
    public function admin() {}
}"""
    nodes = [
        Node(
            id="c1",
            kind=NodeKind.CLASS,
            name="MyController",
            qualified_name="MyController",
            file_path="test.php",
            start_line=2,
            end_line=5,
            language="php",
        )
    ]
    patterns = detector.detect("test.php", None, source, nodes, [])
    assert len(patterns) > 0


def test_paren_depth(detector):
    source = b"""<?php
class MyService {
    public function __construct(
        array $options = array('a' => array(1))
    ) {}
}"""
    detector.detect("test.php", None, source, [], [])
