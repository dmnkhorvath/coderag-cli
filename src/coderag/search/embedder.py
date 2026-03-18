"""Code Embedder — convert code nodes to vector embeddings.

Uses fastembed (ONNX Runtime) to produce dense vector representations
of code symbols for semantic search.  No PyTorch or remote HuggingFace
dependency required — models run locally via ONNX.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from coderag.search import require_semantic

if TYPE_CHECKING:
    from fastembed import TextEmbedding

    from coderag.core.models import Node

logger = logging.getLogger(__name__)

# Default model — small, fast, 384 dimensions, runs locally via ONNX
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Mapping for backward compatibility: short names -> fastembed names
_MODEL_ALIASES: dict[str, str] = {
    "all-MiniLM-L6-v2": "sentence-transformers/all-MiniLM-L6-v2",
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
    "bge-small-en": "BAAI/bge-small-en",
}


class CodeEmbedder:
    """Produce vector embeddings for code graph nodes.

    The underlying *fastembed* ONNX model is loaded lazily on
    first use so that importing this module is essentially free.

    Models run **locally** via ONNX Runtime — no PyTorch or remote
    HuggingFace API calls required.

    Args:
        model_name: Model identifier.  Accepts fastembed full names
            (e.g. ``sentence-transformers/all-MiniLM-L6-v2``) or short
            aliases (e.g. ``all-MiniLM-L6-v2``).  Defaults to
            ``sentence-transformers/all-MiniLM-L6-v2`` (384-d, ~90 MB ONNX).
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name = _MODEL_ALIASES.get(model_name, model_name)
        self._model: TextEmbedding | None = None
        self._dimension: int | None = None

    # ── Properties ────────────────────────────────────────────

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        """Embedding dimensionality (loads model if needed)."""
        if self._dimension is None:
            self._get_model()
        return self._dimension  # type: ignore[return-value]

    # ── Lazy model loading ────────────────────────────────────

    def _get_model(self) -> TextEmbedding:
        if self._model is None:
            require_semantic()
            from fastembed import TextEmbedding

            logger.info("Loading embedding model (ONNX): %s", self._model_name)
            self._model = TextEmbedding(model_name=self._model_name)
            # Determine dimension from a probe embedding
            probe = list(self._model.embed(["dimension probe"]))[0]
            self._dimension = probe.shape[0]
            logger.info(
                "Model loaded — dimension=%d (ONNX Runtime, local)",
                self._dimension,
            )
        return self._model

    # ── Text construction ─────────────────────────────────────

    @staticmethod
    def build_node_text(node: Node, parent_name: str | None = None) -> str:
        """Build a searchable text representation of a graph node.

        Combines the node's kind, name, file path, docstring,
        signature information, and parent context into a single
        string suitable for embedding.

        Args:
            node: The graph node to represent.
            parent_name: Optional parent symbol name for context
                (e.g. the class name for a method).

        Returns:
            A descriptive text string.
        """
        parts: list[str] = []

        # Kind and name
        kind_str = node.kind.value if hasattr(node.kind, "value") else str(node.kind)
        parts.append(f"{kind_str}: {node.name}")

        # File path context
        if node.file_path:
            parts.append(f"in {node.file_path}")

        # Parent context
        if parent_name:
            parts.append(f"({kind_str} of {parent_name})")

        # Qualified name (if different from name)
        if node.qualified_name and node.qualified_name != node.name:
            parts.append(f"[{node.qualified_name}]")

        # Docblock / docstring
        if node.docblock:
            # Truncate very long docblocks
            doc = node.docblock.strip()
            if len(doc) > 500:
                doc = doc[:500] + "..."
            parts.append(f". {doc}")

        # Metadata: parameters, return type, decorators
        meta = node.metadata or {}

        params = meta.get("parameters") or meta.get("params")
        if params:
            if isinstance(params, list):
                param_str = ", ".join(p if isinstance(p, str) else p.get("name", str(p)) for p in params)
            else:
                param_str = str(params)
            parts.append(f". Parameters: {param_str}")

        return_type = meta.get("return_type") or meta.get("returns")
        if return_type:
            parts.append(f". Returns: {return_type}")

        decorators = meta.get("decorators")
        if decorators:
            if isinstance(decorators, list):
                dec_str = ", ".join(str(d) for d in decorators)
            else:
                dec_str = str(decorators)
            parts.append(f". Decorators: {dec_str}")

        # Superclasses / interfaces
        extends = meta.get("extends") or meta.get("superclass")
        if extends:
            parts.append(f". Extends: {extends}")

        implements = meta.get("implements")
        if implements:
            if isinstance(implements, list):
                impl_str = ", ".join(str(i) for i in implements)
            else:
                impl_str = str(implements)
            parts.append(f". Implements: {impl_str}")

        return " ".join(parts)

    # ── Embedding ─────────────────────────────────────────────

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string.

        Returns:
            1-D float32 array of shape ``(dimension,)``.
        """
        model = self._get_model()
        vecs = list(model.embed([text]))
        return np.asarray(vecs[0], dtype=np.float32)

    def embed_batch(self, texts: list[str], batch_size: int = 128) -> np.ndarray:
        """Embed a batch of texts efficiently.

        Args:
            texts: List of text strings to embed.
            batch_size: Encoding batch size (passed to the model).

        Returns:
            2-D float32 array of shape ``(len(texts), dimension)``.
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)

        model = self._get_model()
        vecs = list(model.embed(texts, batch_size=batch_size))
        return np.asarray(vecs, dtype=np.float32)
