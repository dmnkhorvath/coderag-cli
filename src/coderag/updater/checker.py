"""Version checking with caching for CodeRAG updates."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_CACHE_FILE, UpdateConfig


@dataclass
class VersionInfo:
    """Information about an available version."""

    current: str
    latest: str
    update_available: bool
    release_url: str = ""
    release_notes: str = ""
    published_at: str = ""
    is_prerelease: bool = False


class UpdateChecker:
    """Check for CodeRAG updates via GitHub API."""

    GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
    GITHUB_TAGS_API = "https://api.github.com/repos/{repo}/tags"

    def __init__(
        self,
        config: UpdateConfig | None = None,
        cache_path: Path | None = None,
    ):
        self.config = config or UpdateConfig()
        self.cache_path = cache_path or DEFAULT_CACHE_FILE

    def get_current_version(self) -> str:
        """Get the currently installed version."""
        try:
            from coderag import __version__

            return __version__
        except (ImportError, AttributeError):
            return "0.0.0"

    def check(self, force: bool = False) -> VersionInfo | None:
        """Check for updates. Uses cache unless force=True or cache expired."""
        if not force:
            cached = self._load_cache()
            if cached:
                return cached

        current = self.get_current_version()
        latest_info = self._fetch_latest()

        if latest_info is None:
            return None

        latest_version = latest_info.get("tag_name", "").lstrip("v")
        if not latest_version:
            return None

        info = VersionInfo(
            current=current,
            latest=latest_version,
            update_available=self._compare_versions(current, latest_version),
            release_url=latest_info.get("html_url", ""),
            release_notes=latest_info.get("body", "")[:500] if latest_info.get("body") else "",
            published_at=latest_info.get("published_at", ""),
            is_prerelease=latest_info.get("prerelease", False),
        )

        self._save_cache(info)
        return info

    def _fetch_latest(self) -> dict | None:
        """Fetch latest release info from GitHub API."""
        url = self.GITHUB_API.format(repo=self.config.github_repo)
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "CodeRAG-Updater",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
            return None

    def _fetch_latest_tag(self) -> str | None:
        """Fallback: fetch latest tag if no releases exist."""
        url = self.GITHUB_TAGS_API.format(repo=self.config.github_repo)
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "CodeRAG-Updater",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                tags = json.loads(resp.read().decode())
                if tags:
                    return tags[0].get("name", "").lstrip("v")
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            OSError,
        ):
            pass
        return None

    @staticmethod
    def _compare_versions(current: str, latest: str) -> bool:
        """Return True if latest > current using semantic versioning."""
        try:

            def parse_ver(v: str) -> tuple:
                parts = v.split(".")
                return tuple(int(p) for p in parts[:3])

            return parse_ver(latest) > parse_ver(current)
        except (ValueError, IndexError):
            return False

    def _load_cache(self) -> VersionInfo | None:
        """Load cached version info if still valid."""
        if not self.cache_path.exists():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > self.config.check_interval:
                return None
            current = self.get_current_version()
            return VersionInfo(
                current=current,
                latest=data.get("latest", "0.0.0"),
                update_available=self._compare_versions(current, data.get("latest", "0.0.0")),
                release_url=data.get("release_url", ""),
                release_notes=data.get("release_notes", ""),
                published_at=data.get("published_at", ""),
                is_prerelease=data.get("is_prerelease", False),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _save_cache(self, info: VersionInfo) -> None:
        """Save version info to cache."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cached_at": time.time(),
            "latest": info.latest,
            "release_url": info.release_url,
            "release_notes": info.release_notes,
            "published_at": info.published_at,
            "is_prerelease": info.is_prerelease,
        }
        self.cache_path.write_text(json.dumps(data, indent=2))

    def clear_cache(self) -> None:
        """Remove the cache file."""
        if self.cache_path.exists():
            self.cache_path.unlink()
