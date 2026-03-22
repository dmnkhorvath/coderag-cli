"""Auto-Update System for CodeRAG.

Provides version checking, update installation, and configuration
management for keeping CodeRAG up to date.
"""

from coderag.updater.checker import UpdateChecker, VersionInfo
from coderag.updater.config import UpdateConfig
from coderag.updater.installer import UpdateInstaller, UpdateResult, UpdateStrategy

__all__ = [
    "UpdateChecker",
    "UpdateConfig",
    "UpdateInstaller",
    "UpdateResult",
    "UpdateStrategy",
    "VersionInfo",
]
