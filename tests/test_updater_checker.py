"""Tests for updater checker module."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

from coderag.updater.checker import UpdateChecker, VersionInfo
from coderag.updater.config import UpdateConfig


class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_version_info_fields(self):
        info = VersionInfo(
            current="0.1.0",
            latest="0.2.0",
            update_available=True,
            release_url="https://example.com",
            release_notes="Bug fixes",
            published_at="2026-01-01",
            is_prerelease=False,
        )
        assert info.current == "0.1.0"
        assert info.latest == "0.2.0"
        assert info.update_available is True
        assert info.release_url == "https://example.com"

    def test_version_info_defaults(self):
        info = VersionInfo(current="0.1.0", latest="0.1.0", update_available=False)
        assert info.release_url == ""
        assert info.release_notes == ""
        assert info.published_at == ""
        assert info.is_prerelease is False


class TestGetCurrentVersion:
    """Tests for get_current_version."""

    def test_returns_version_string(self):
        checker = UpdateChecker()
        version = checker.get_current_version()
        assert isinstance(version, str)
        assert "." in version

    def test_returns_installed_version(self):
        checker = UpdateChecker()
        version = checker.get_current_version()
        assert version == "0.1.0"


class TestCompareVersions:
    """Tests for _compare_versions."""

    def test_newer_patch(self):
        assert UpdateChecker._compare_versions("1.0.0", "1.0.1") is True

    def test_same_version(self):
        assert UpdateChecker._compare_versions("1.0.0", "1.0.0") is False

    def test_older_version(self):
        assert UpdateChecker._compare_versions("2.0.0", "1.9.9") is False

    def test_newer_minor(self):
        assert UpdateChecker._compare_versions("0.1.0", "0.2.0") is True

    def test_newer_major(self):
        assert UpdateChecker._compare_versions("0.9.9", "1.0.0") is True

    def test_invalid_current(self):
        assert UpdateChecker._compare_versions("invalid", "1.0.0") is False

    def test_invalid_latest(self):
        assert UpdateChecker._compare_versions("1.0.0", "invalid") is False

    def test_both_invalid(self):
        assert UpdateChecker._compare_versions("abc", "xyz") is False

    def test_empty_strings(self):
        assert UpdateChecker._compare_versions("", "") is False


class TestCheckWithMock:
    """Tests for check method with mocked HTTP."""

    def _mock_response(self, data: dict):
        """Create a mock urlopen response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_check_with_update_available(self, mock_urlopen, tmp_path):
        mock_urlopen.return_value = self._mock_response(
            {
                "tag_name": "v1.0.0",
                "html_url": "https://github.com/test/releases/v1.0.0",
                "body": "Release notes here",
                "published_at": "2026-01-01T00:00:00Z",
                "prerelease": False,
            }
        )
        config = UpdateConfig()
        checker = UpdateChecker(config, cache_path=tmp_path / "cache.json")
        info = checker.check(force=True)
        assert info is not None
        assert info.update_available is True
        assert info.latest == "1.0.0"
        assert info.release_url == "https://github.com/test/releases/v1.0.0"

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_check_no_update(self, mock_urlopen, tmp_path):
        mock_urlopen.return_value = self._mock_response(
            {
                "tag_name": "v0.1.0",
                "html_url": "https://github.com/test/releases/v0.1.0",
                "body": "",
                "published_at": "2026-01-01T00:00:00Z",
                "prerelease": False,
            }
        )
        config = UpdateConfig()
        checker = UpdateChecker(config, cache_path=tmp_path / "cache.json")
        info = checker.check(force=True)
        assert info is not None
        assert info.update_available is False

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_check_network_error_returns_none(self, mock_urlopen, tmp_path):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        config = UpdateConfig()
        checker = UpdateChecker(config, cache_path=tmp_path / "cache.json")
        info = checker.check(force=True)
        assert info is None

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_check_empty_tag_returns_none(self, mock_urlopen, tmp_path):
        mock_urlopen.return_value = self._mock_response(
            {
                "tag_name": "",
                "html_url": "",
            }
        )
        config = UpdateConfig()
        checker = UpdateChecker(config, cache_path=tmp_path / "cache.json")
        info = checker.check(force=True)
        assert info is None

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_check_prerelease(self, mock_urlopen, tmp_path):
        mock_urlopen.return_value = self._mock_response(
            {
                "tag_name": "v2.0.0-beta.1",
                "html_url": "https://github.com/test/releases/v2.0.0-beta.1",
                "body": "Beta release",
                "published_at": "2026-01-01T00:00:00Z",
                "prerelease": True,
            }
        )
        config = UpdateConfig()
        checker = UpdateChecker(config, cache_path=tmp_path / "cache.json")
        info = checker.check(force=True)
        assert info is not None
        assert info.is_prerelease is True


class TestCache:
    """Tests for cache save and load."""

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_cache_save_and_load(self, mock_urlopen, tmp_path):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "tag_name": "v1.0.0",
                "html_url": "https://example.com",
                "body": "Notes",
                "published_at": "2026-01-01",
                "prerelease": False,
            }
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        cache_path = tmp_path / "cache.json"
        config = UpdateConfig(check_interval=3600)
        checker = UpdateChecker(config, cache_path=cache_path)

        # First check fetches from network
        info1 = checker.check(force=True)
        assert info1 is not None
        assert cache_path.exists()

        # Second check uses cache (no network call)
        mock_urlopen.reset_mock()
        info2 = checker.check(force=False)
        assert info2 is not None
        assert info2.latest == "1.0.0"
        mock_urlopen.assert_not_called()

    def test_cache_expiry(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_data = {
            "cached_at": time.time() - 7200,  # 2 hours ago
            "latest": "1.0.0",
            "release_url": "",
            "release_notes": "",
            "published_at": "",
            "is_prerelease": False,
        }
        cache_path.write_text(json.dumps(cache_data))

        config = UpdateConfig(check_interval=3600)  # 1 hour
        checker = UpdateChecker(config, cache_path=cache_path)
        cached = checker._load_cache()
        assert cached is None  # Cache expired

    def test_cache_valid(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_data = {
            "cached_at": time.time(),  # Just now
            "latest": "1.0.0",
            "release_url": "https://example.com",
            "release_notes": "Notes",
            "published_at": "2026-01-01",
            "is_prerelease": False,
        }
        cache_path.write_text(json.dumps(cache_data))

        config = UpdateConfig(check_interval=3600)
        checker = UpdateChecker(config, cache_path=cache_path)
        cached = checker._load_cache()
        assert cached is not None
        assert cached.latest == "1.0.0"

    def test_cache_corrupted_returns_none(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("not valid json")
        checker = UpdateChecker(cache_path=cache_path)
        cached = checker._load_cache()
        assert cached is None

    def test_clear_cache(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_path.write_text(json.dumps({"cached_at": time.time(), "latest": "1.0.0"}))
        checker = UpdateChecker(cache_path=cache_path)
        checker.clear_cache()
        assert not cache_path.exists()

    def test_clear_cache_nonexistent(self, tmp_path):
        cache_path = tmp_path / "nonexistent.json"
        checker = UpdateChecker(cache_path=cache_path)
        checker.clear_cache()  # Should not raise

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_force_bypasses_cache(self, mock_urlopen, tmp_path):
        cache_path = tmp_path / "cache.json"
        cache_data = {
            "cached_at": time.time(),
            "latest": "0.5.0",
            "release_url": "",
            "release_notes": "",
            "published_at": "",
            "is_prerelease": False,
        }
        cache_path.write_text(json.dumps(cache_data))

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "tag_name": "v2.0.0",
                "html_url": "",
                "body": "",
                "published_at": "",
                "prerelease": False,
            }
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        config = UpdateConfig(check_interval=3600)
        checker = UpdateChecker(config, cache_path=cache_path)
        info = checker.check(force=True)
        assert info is not None
        assert info.latest == "2.0.0"
        mock_urlopen.assert_called_once()


class TestFetchLatestTag:
    """Tests for _fetch_latest_tag fallback."""

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_fetch_latest_tag_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            [
                {"name": "v1.2.3"},
                {"name": "v1.2.2"},
            ]
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        checker = UpdateChecker()
        tag = checker._fetch_latest_tag()
        assert tag == "1.2.3"

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_fetch_latest_tag_network_error(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("error")
        checker = UpdateChecker()
        tag = checker._fetch_latest_tag()
        assert tag is None

    @patch("coderag.updater.checker.urllib.request.urlopen")
    def test_fetch_latest_tag_empty_list(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([]).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        checker = UpdateChecker()
        tag = checker._fetch_latest_tag()
        assert tag is None
