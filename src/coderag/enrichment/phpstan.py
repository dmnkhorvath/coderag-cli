import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from coderag.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PHPStanResult:
    file_path: str
    line: int
    message: str
    identifier: str | None = None
    tip: str | None = None
    ignorable: bool = True


@dataclass
class EnrichmentReport:
    files_analyzed: int = 0
    errors_found: int = 0
    nodes_enriched: int = 0
    duration_ms: float = 0.0
    phpstan_version: str = ""
    skipped_reason: str | None = None
    level: int = 5


class PHPStanEnricher:
    """Enriches PHP nodes with type information from PHPStan."""

    def __init__(self, project_root: str | Path, phpstan_path: str = "phpstan", level: int = 5):
        self._project_root = Path(project_root)
        self._phpstan_path = phpstan_path
        self.level = max(0, min(9, level))  # Clamp between 0 and 9
        self._version = ""
        self._last_results: dict[str, list[PHPStanResult]] = {}

    @property
    def project_root(self) -> str:
        return str(self._project_root)

    @property
    def phpstan_path(self) -> str:
        return self._phpstan_path

    def get_version(self) -> str:
        if not self._version:
            self.is_available()
        match = re.search(r"(\d+\.\d+\.\d+)", self._version)
        if match:
            return match.group(1)
        return self._version

    def is_available(self) -> bool:
        """Check if PHPStan is available in the environment or vendor dir."""
        # Check global/path
        try:
            result = subprocess.run([self._phpstan_path, "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self._version = result.stdout.strip()
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check local vendor
        vendor_path = self._project_root / "vendor" / "bin" / "phpstan"
        try:
            result = subprocess.run([str(vendor_path), "--version"], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self._phpstan_path = str(vendor_path)
                self._version = result.stdout.strip()
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return False

    def _parse_json_output(self, output: str) -> dict[str, list[PHPStanResult]]:
        if not output.strip():
            return {}

        try:
            start_idx = output.find("{")
            if start_idx >= 0:
                json_str = output[start_idx:]
                data = json.loads(json_str)
            else:
                return {}
        except json.JSONDecodeError:
            return {}

        results: dict[str, list[PHPStanResult]] = {}
        for file_path, file_data in data.get("files", {}).items():
            rel_path = file_path
            if rel_path.startswith(str(self._project_root)):
                rel_path = os.path.relpath(rel_path, str(self._project_root))

            file_results = []
            for msg in file_data.get("messages", []):
                file_results.append(
                    PHPStanResult(
                        file_path=rel_path,
                        line=msg.get("line", 0),
                        message=msg.get("message", ""),
                        identifier=msg.get("identifier"),
                        tip=msg.get("tip"),
                        ignorable=msg.get("ignorable", True),
                    )
                )
            if file_results:
                results[rel_path] = file_results
        return results

    def analyze(self, files: list[str] | None = None) -> dict[str, list[PHPStanResult]]:
        """Run PHPStan analysis and parse JSON output."""
        if not self.is_available():
            raise RuntimeError("PHPStan is not available")

        cmd = [self._phpstan_path, "analyse", "--error-format=json", f"--level={self.level}", "--no-progress"]

        if files:
            cmd.extend(files)
        else:
            cmd.append(str(self._project_root))

        logger.info(f"Running PHPStan: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, cwd=str(self._project_root), capture_output=True, text=True, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.error(f"PHPStan executable not found at {self._phpstan_path}")
            return {}

        if not result.stdout.strip():
            logger.warning("PHPStan returned empty output.")
            return {}

        results = self._parse_json_output(result.stdout)
        if not results and result.stdout.strip() and not result.stdout.strip().startswith("{"):
            logger.error(f"Failed to parse PHPStan JSON output: {result.stdout[:200]}")

        return results

    def enrich_nodes(self, store: SQLiteStore, files: list[str] | None = None) -> EnrichmentReport:
        """Run analysis and update nodes in the store with type information."""
        start_time = time.time()
        report = EnrichmentReport(level=self.level)

        if not self.is_available():
            logger.warning("PHPStan is not available. Skipping enrichment.")
            report.skipped_reason = "PHPStan not available"
            return report

        report.phpstan_version = self.get_version()

        if not self._last_results:
            self._last_results = self.analyze(files)

        report.files_analyzed = len(self._last_results)
        report.errors_found = sum(len(r) for r in self._last_results.values())

        nodes_to_update = []
        for file_path, file_results in self._last_results.items():
            nodes = store.find_nodes(file_path=file_path)
            if not nodes:
                nodes = store.find_nodes(file_path=os.path.basename(file_path))
            if not nodes:
                continue

            for res in file_results:
                for node in nodes:
                    if node.start_line <= res.line <= node.end_line:
                        type_info = _extract_type_from_message(res.message)

                        if not hasattr(node, "metadata") or node.metadata is None:
                            node.metadata = {}

                        if "phpstan" not in node.metadata:
                            node.metadata["phpstan"] = {"errors": [], "types": {}, "issue_count": 0}

                        if "errors" not in node.metadata["phpstan"]:
                            node.metadata["phpstan"]["errors"] = []
                        if "types" not in node.metadata["phpstan"]:
                            node.metadata["phpstan"]["types"] = {}
                        if "issue_count" not in node.metadata["phpstan"]:
                            node.metadata["phpstan"]["issue_count"] = 0

                        node.metadata["phpstan"]["errors"].append(res.message)
                        node.metadata["phpstan"]["issue_count"] += 1

                        if type_info:
                            node.metadata["phpstan"]["types"].update(type_info)

                        if node not in nodes_to_update:
                            nodes_to_update.append(node)
                            report.nodes_enriched += 1

        if nodes_to_update:
            store.upsert_nodes(nodes_to_update)

        report.duration_ms = (time.time() - start_time) * 1000
        return report


def _extract_type_from_message(message: str) -> dict:
    """Extract type information from a PHPStan error message."""
    info = {}
    if "deprecated class" in message:
        info["deprecated_type"] = True
    if "should return" in message and "but returns" in message:
        parts = message.split("should return ")[1].split(" but returns")
        info["expected_return_type"] = parts[0].strip()
        info["actual_return_type"] = parts[1].strip().rstrip(".")
    if "has no return type specified" in message:
        info["missing"] = "return_type"
    if "has no type specified" in message:
        if "Parameter" in message:
            info["missing"] = "parameter_type"
            parts = message.split("Parameter ")[1].split(" of method")
            info["parameter_name"] = parts[0].strip()
        elif "Property" in message:
            info["missing"] = "property_type"
    if "expects" in message and "given" in message:
        parts = message.split("expects ")[1].split(",")
        info["expected_type"] = parts[0].strip()
    if "return type has no value type specified" in message:
        info["missing"] = "return_value_type"
    if "PHPDoc tag @return with type" in message:
        parts = message.split("with type ")[1].split(" is not subtype")
        info["phpdoc_return_type"] = parts[0].strip()
    if "PHPDoc tag @param" in message and "with type" in message:
        parts = message.split("with type ")[1].split(" is not subtype")
        info["phpdoc_param_type"] = parts[0].strip()
    return info
