"""Update installation for CodeRAG."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class UpdateStrategy(Enum):
    """Strategy for installing updates."""

    PYPI = "pypi"
    GIT = "git"


@dataclass
class UpdateResult:
    """Result of an update attempt."""

    success: bool
    strategy: UpdateStrategy
    old_version: str
    new_version: str
    message: str
    output: str = ""


class UpdateInstaller:
    """Install CodeRAG updates."""

    def __init__(self, strategy: UpdateStrategy | None = None):
        self.strategy = strategy or self._detect_strategy()

    def _detect_strategy(self) -> UpdateStrategy:
        """Detect whether we are installed via pip or git."""
        coderag_dir = Path(__file__).parent.parent
        if (coderag_dir.parent.parent / ".git").exists():
            return UpdateStrategy.GIT
        return UpdateStrategy.PYPI

    def install(self, target_version: str | None = None) -> UpdateResult:
        """Run the update."""
        from .checker import UpdateChecker

        checker = UpdateChecker()
        old_version = checker.get_current_version()

        if self.strategy == UpdateStrategy.PYPI:
            return self._install_pypi(old_version, target_version)
        return self._install_git(old_version, target_version)

    def _install_pypi(self, old_version: str, target_version: str | None = None) -> UpdateResult:
        """Update via pip."""
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade"]
        if target_version:
            cmd.append(f"coderag=={target_version}")
        else:
            cmd.append("coderag")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                new_version = self._get_installed_version()
                return UpdateResult(
                    success=True,
                    strategy=UpdateStrategy.PYPI,
                    old_version=old_version,
                    new_version=new_version,
                    message=f"Updated from {old_version} to {new_version}",
                    output=result.stdout,
                )
            return UpdateResult(
                success=False,
                strategy=UpdateStrategy.PYPI,
                old_version=old_version,
                new_version=old_version,
                message=f"pip install failed: {result.stderr[:300]}",
                output=result.stderr,
            )
        except subprocess.TimeoutExpired:
            return UpdateResult(
                success=False,
                strategy=UpdateStrategy.PYPI,
                old_version=old_version,
                new_version=old_version,
                message="Update timed out after 120 seconds",
            )

    def _install_git(self, old_version: str, target_version: str | None = None) -> UpdateResult:
        """Update via git pull + pip install."""
        repo_root = Path(__file__).parent.parent.parent.parent

        try:
            pull_result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(repo_root),
            )
            if pull_result.returncode != 0:
                return UpdateResult(
                    success=False,
                    strategy=UpdateStrategy.GIT,
                    old_version=old_version,
                    new_version=old_version,
                    message=f"git pull failed: {pull_result.stderr[:300]}",
                    output=pull_result.stderr,
                )

            pip_result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".[all]"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(repo_root),
            )
            if pip_result.returncode != 0:
                return UpdateResult(
                    success=False,
                    strategy=UpdateStrategy.GIT,
                    old_version=old_version,
                    new_version=old_version,
                    message=f"pip install failed after git pull: {pip_result.stderr[:300]}",
                    output=pip_result.stderr,
                )

            new_version = self._get_installed_version()
            return UpdateResult(
                success=True,
                strategy=UpdateStrategy.GIT,
                old_version=old_version,
                new_version=new_version,
                message=f"Updated from {old_version} to {new_version} via git",
                output=pull_result.stdout + "\n" + pip_result.stdout,
            )
        except subprocess.TimeoutExpired:
            return UpdateResult(
                success=False,
                strategy=UpdateStrategy.GIT,
                old_version=old_version,
                new_version=old_version,
                message="Update timed out",
            )

    @staticmethod
    def _get_installed_version() -> str:
        """Get the currently installed version (fresh import)."""
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from coderag import __version__; print(__version__)",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() or "unknown"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "unknown"
