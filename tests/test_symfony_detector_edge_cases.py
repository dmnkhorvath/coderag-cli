import pytest

from coderag.plugins.php.frameworks.symfony import SymfonyDetector


@pytest.fixture
def detector():
    return SymfonyDetector()


def test_not_php(detector):
    assert detector.detect("test.txt", None, b"", [], []) == []


def test_construct_no_class(detector):
    source = b"""<?php
    public function __construct(private LoggerInterface $logger) {}
    """
    detector.detect("test.php", None, source, [], [])


def test_event_listener_no_class(detector):
    source = b"""<?php
    #[AsEventListener(event: 'kernel.request')]
    public function onKernelRequest() {}
    """
    detector.detect("test.php", None, source, [], [])


def test_event_subscriber(detector):
    source = b"""<?php
    class MySubscriber implements EventSubscriberInterface {
    }
    """
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0
