import json

import pytest

from coderag.plugins.php.frameworks.symfony import SymfonyDetector


@pytest.fixture
def detector():
    return SymfonyDetector()


def test_detect_framework_composer(detector, tmp_path):
    composer_file = tmp_path / "composer.json"
    composer_file.write_text(json.dumps({"require": {"symfony/framework-bundle": "^6.0"}}))
    assert detector.detect_framework(str(tmp_path))


def test_detect_framework_composer_invalid(detector, tmp_path):
    composer_file = tmp_path / "composer.json"
    composer_file.write_text("{invalid json")
    assert not detector.detect_framework(str(tmp_path))


def test_detect_framework_bundles(detector, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "bundles.php").touch()
    assert detector.detect_framework(str(tmp_path))


def test_detect_template_attribute(detector):
    source = b"""<?php
class MyController {
    #[Template('users/list.html.twig')]
    public function list() {}
}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0


def test_detect_commands_fallback(detector):
    source = b"""<?php
#[AsCommand(name: 'app:create-user')]
class CreateUserCommand {}"""
    patterns = detector.detect("test.php", None, source, [], [])
    assert len(patterns) > 0
