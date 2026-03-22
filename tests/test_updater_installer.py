"""Tests for updater installer module."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

from coderag.updater.installer import UpdateInstaller, UpdateResult, UpdateStrategy


class TestDetectStrategy:
    """Tests for _detect_strategy."""

    def test_explicit_pypi_strategy(self):
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        assert installer.strategy == UpdateStrategy.PYPI

    def test_explicit_git_strategy(self):
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        assert installer.strategy == UpdateStrategy.GIT

    def test_detect_strategy_returns_valid(self):
        installer = UpdateInstaller()
        assert installer.strategy in (UpdateStrategy.PYPI, UpdateStrategy.GIT)

    def test_detect_strategy_returns_git_for_coderag_repo(self):
        """Since we are in a git repo, strategy should be GIT."""
        installer = UpdateInstaller()
        assert installer.strategy == UpdateStrategy.GIT


class TestInstallPypi:
    """Tests for _install_pypi with mocked subprocess."""

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_pypi_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Successfully installed coderag-1.0.0", stderr=""),
            MagicMock(returncode=0, stdout="1.0.0\n", stderr=""),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        result = installer._install_pypi("0.1.0")
        assert result.success is True
        assert result.strategy == UpdateStrategy.PYPI
        assert result.old_version == "0.1.0"
        assert result.new_version == "1.0.0"

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_pypi_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: No matching distribution")
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        result = installer._install_pypi("0.1.0")
        assert result.success is False
        assert "pip install failed" in result.message

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_pypi_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pip", timeout=120)
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        result = installer._install_pypi("0.1.0")
        assert result.success is False
        assert "timed out" in result.message

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_pypi_with_target_version(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="OK", stderr=""),
            MagicMock(returncode=0, stdout="0.5.0\n", stderr=""),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        result = installer._install_pypi("0.1.0", target_version="0.5.0")
        assert result.success is True
        call_args = mock_run.call_args_list[0]
        cmd = call_args[0][0]
        assert any("coderag==0.5.0" in arg for arg in cmd)


class TestInstallGit:
    """Tests for _install_git with mocked subprocess."""

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_git_success(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Already up to date.\n", stderr=""),
            MagicMock(returncode=0, stdout="Successfully installed\n", stderr=""),
            MagicMock(returncode=0, stdout="1.0.0\n", stderr=""),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        result = installer._install_git("0.1.0")
        assert result.success is True
        assert result.strategy == UpdateStrategy.GIT

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_git_pull_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fatal: not a git repository")
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        result = installer._install_git("0.1.0")
        assert result.success is False
        assert "git pull failed" in result.message

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_git_pip_failure(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Updated\n", stderr=""),
            MagicMock(returncode=1, stdout="", stderr="ERROR: pip failed"),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        result = installer._install_git("0.1.0")
        assert result.success is False
        assert "pip install failed after git pull" in result.message

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_git_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=60)
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        result = installer._install_git("0.1.0")
        assert result.success is False
        assert "timed out" in result.message


class TestGetInstalledVersion:
    """Tests for _get_installed_version."""

    @patch("coderag.updater.installer.subprocess.run")
    def test_get_installed_version_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="0.2.0\n", stderr="")
        version = UpdateInstaller._get_installed_version()
        assert version == "0.2.0"

    @patch("coderag.updater.installer.subprocess.run")
    def test_get_installed_version_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="\n", stderr="")
        version = UpdateInstaller._get_installed_version()
        assert version == "unknown"

    @patch("coderag.updater.installer.subprocess.run")
    def test_get_installed_version_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=10)
        version = UpdateInstaller._get_installed_version()
        assert version == "unknown"


class TestUpdateResult:
    """Tests for UpdateResult dataclass."""

    def test_update_result_fields(self):
        result = UpdateResult(
            success=True,
            strategy=UpdateStrategy.PYPI,
            old_version="0.1.0",
            new_version="0.2.0",
            message="Updated successfully",
            output="pip output here",
        )
        assert result.success is True
        assert result.strategy == UpdateStrategy.PYPI
        assert result.old_version == "0.1.0"
        assert result.new_version == "0.2.0"
        assert result.output == "pip output here"

    def test_update_result_default_output(self):
        result = UpdateResult(
            success=False,
            strategy=UpdateStrategy.GIT,
            old_version="0.1.0",
            new_version="0.1.0",
            message="Failed",
        )
        assert result.output == ""


class TestInstallMethod:
    """Tests for the install() method."""

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_dispatches_to_pypi(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="OK", stderr=""),
            MagicMock(returncode=0, stdout="1.0.0\n", stderr=""),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.PYPI)
        result = installer.install()
        assert result.strategy == UpdateStrategy.PYPI

    @patch("coderag.updater.installer.subprocess.run")
    def test_install_dispatches_to_git(self, mock_run):
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="OK", stderr=""),
            MagicMock(returncode=0, stdout="OK", stderr=""),
            MagicMock(returncode=0, stdout="1.0.0\n", stderr=""),
        ]
        installer = UpdateInstaller(strategy=UpdateStrategy.GIT)
        result = installer.install()
        assert result.strategy == UpdateStrategy.GIT
