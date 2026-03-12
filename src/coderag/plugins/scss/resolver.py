"""SCSS module resolver for CodeRAG.

Handles SCSS-specific module resolution:
- @use/@forward/@import path resolution
- SCSS partial resolution (_partial.scss convention)
- Index file resolution (path/index.scss, path/_index.scss)
- Namespace resolution for @use ... as namespace
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from coderag.core.models import FileInfo, ResolutionResult, ResolutionStrategy
from coderag.core.registry import ModuleResolver

logger = logging.getLogger(__name__)

# Extensions to try when resolving SCSS imports
_SCSS_EXTENSIONS = (".scss", ".sass", ".css")


class SCSSResolver(ModuleResolver):
    """Resolves SCSS cross-file references.

    Implements the SCSS module resolution algorithm:
    1. Try exact path
    2. Try with SCSS extensions (.scss, .sass, .css)
    3. Try partial convention (_filename.scss)
    4. Try as directory with index file (path/index.scss, path/_index.scss)
    """

    def __init__(self) -> None:
        self._project_root: Path = Path(".")
        self._scss_files: dict[str, str] = {}  # relative_path -> absolute_path
        self._file_basenames: dict[str, list[str]] = {}  # basename -> [relative_paths]

    def set_project_root(self, project_root: str) -> None:
        """Set the project root for path resolution."""
        self._project_root = Path(project_root)

    def build_index(self, files: Sequence[FileInfo]) -> None:
        """Build index of SCSS/CSS files for resolution."""
        self._scss_files.clear()
        self._file_basenames.clear()

        for fi in files:
            self._scss_files[fi.relative_path] = fi.path
            basename = Path(fi.relative_path).name
            self._file_basenames.setdefault(basename, []).append(fi.relative_path)

        logger.debug("SCSS resolver indexed %d files", len(self._scss_files))

    def resolve(
        self,
        import_path: str,
        from_file: str,
        context: dict[str, Any] | None = None,
    ) -> ResolutionResult:
        """Resolve an SCSS @use/@forward/@import path to a concrete file.

        Args:
            import_path: The import specifier (e.g., "variables", "../mixins").
            from_file: Relative path of the file containing the import.
            context: Additional context (e.g., {"type": "scss_use"}).

        Returns:
            ResolutionResult with resolved path and confidence.
        """
        # Skip external URLs
        if import_path.startswith(("http://", "https://", "//")):
            return ResolutionResult(
                resolved_path=None,
                confidence=0.0,
                resolution_strategy=ResolutionStrategy.UNRESOLVED,
                is_external=True,
                package_name=import_path,
            )

        # Skip data URIs
        if import_path.startswith("data:"):
            return ResolutionResult(
                resolved_path=None,
                confidence=0.0,
                resolution_strategy=ResolutionStrategy.UNRESOLVED,
                is_external=True,
            )

        from_dir = Path(from_file).parent

        # Try all resolution strategies in order
        result = self._try_resolve(import_path, from_dir)
        if result:
            return result

        # Fallback: basename matching
        return self._try_basename_match(import_path, from_file)

    def resolve_symbol(
        self,
        symbol_name: str,
        from_file: str,
        context: dict[str, Any] | None = None,
    ) -> ResolutionResult:
        """Resolve an SCSS symbol reference to its definition file.

        Symbol resolution for SCSS is handled at the graph level
        since we need to search across all extracted nodes.
        """
        return ResolutionResult(
            resolved_path=None,
            confidence=0.0,
            resolution_strategy=ResolutionStrategy.UNRESOLVED,
        )

    def _try_resolve(
        self,
        import_path: str,
        from_dir: Path,
    ) -> ResolutionResult | None:
        """Try all SCSS resolution strategies."""
        # Normalize the import path
        target = from_dir / import_path
        target_str = str(target)

        # 1. Exact match
        if target_str in self._scss_files:
            return ResolutionResult(
                resolved_path=target_str,
                confidence=1.0,
                resolution_strategy=ResolutionStrategy.EXACT,
            )

        # 2. Try adding extensions
        for ext in _SCSS_EXTENSIONS:
            candidate = target_str + ext
            if candidate in self._scss_files:
                return ResolutionResult(
                    resolved_path=candidate,
                    confidence=0.95,
                    resolution_strategy=ResolutionStrategy.EXTENSION,
                )

        # 3. Try partial convention: _filename.scss
        parent = target.parent
        name = target.name
        for ext in _SCSS_EXTENSIONS:
            partial = str(parent / f"_{name}{ext}")
            if partial in self._scss_files:
                return ResolutionResult(
                    resolved_path=partial,
                    confidence=0.95,
                    resolution_strategy=ResolutionStrategy.SCSS_PARTIAL,
                )

        # 4. Try as directory with index file
        for index_name in ("index.scss", "_index.scss", "index.sass", "_index.sass"):
            index_path = str(target / index_name)
            if index_path in self._scss_files:
                return ResolutionResult(
                    resolved_path=index_path,
                    confidence=0.9,
                    resolution_strategy=ResolutionStrategy.SCSS_INDEX,
                )

        # 5. Try partial + directory: _filename/index.scss
        for ext in _SCSS_EXTENSIONS:
            partial_dir = str(parent / f"_{name}")
            for index_name in (f"index{ext}", f"_index{ext}"):
                candidate = f"{partial_dir}/{index_name}"
                if candidate in self._scss_files:
                    return ResolutionResult(
                        resolved_path=candidate,
                        confidence=0.85,
                        resolution_strategy=ResolutionStrategy.SCSS_PARTIAL,
                    )

        return None

    def _try_basename_match(
        self,
        import_path: str,
        from_file: str,
    ) -> ResolutionResult:
        """Try matching by basename as a last resort."""
        name = Path(import_path).name

        # Try all possible basenames
        candidates: list[str] = []
        for ext in _SCSS_EXTENSIONS:
            for prefix in ("", "_"):
                basename = f"{prefix}{name}{ext}"
                candidates.extend(self._file_basenames.get(basename, []))

        # Also try exact basename if it has an extension
        if "." in name:
            candidates.extend(self._file_basenames.get(name, []))

        # Deduplicate
        seen: set[str] = set()
        unique: list[str] = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        if len(unique) == 1:
            return ResolutionResult(
                resolved_path=unique[0],
                confidence=0.7,
                resolution_strategy=ResolutionStrategy.HEURISTIC,
            )
        if len(unique) > 1:
            best = self._pick_closest(from_file, unique)
            return ResolutionResult(
                resolved_path=best,
                confidence=0.5,
                resolution_strategy=ResolutionStrategy.HEURISTIC,
            )

        # Unresolved
        return ResolutionResult(
            resolved_path=None,
            confidence=0.0,
            resolution_strategy=ResolutionStrategy.UNRESOLVED,
        )

    def _pick_closest(self, from_file: str, candidates: list[str]) -> str:
        """Pick the candidate path closest to the importing file."""
        from_parts = Path(from_file).parts
        best_score = -1
        best_path = candidates[0]

        for cand in candidates:
            cand_parts = Path(cand).parts
            common = 0
            for a, b in zip(from_parts, cand_parts):
                if a == b:
                    common += 1
                else:
                    break
            if common > best_score:
                best_score = common
                best_path = cand

        return best_path
