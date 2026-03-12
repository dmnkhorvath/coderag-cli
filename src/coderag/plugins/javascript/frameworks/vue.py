"""Vue.js framework detector for CodeRAG.

Detects Vue-specific patterns including Single File Components,
Composition API, Options API, and state management (Vuex/Pinia)
from already-parsed AST nodes and source code.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from coderag.core.models import (
    Edge,
    EdgeKind,
    FrameworkPattern,
    Node,
    NodeKind,
    generate_node_id,
)
from coderag.core.registry import FrameworkDetector

logger = logging.getLogger(__name__)

# ── SFC block detection ───────────────────────────────────────
_TEMPLATE_BLOCK_RE = re.compile(
    r"<template(?P<attrs>[^>]*)>(?P<content>.*?)</template>",
    re.DOTALL,
)
_SCRIPT_BLOCK_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<content>.*?)</script>",
    re.DOTALL,
)
_STYLE_BLOCK_RE = re.compile(
    r"<style(?P<attrs>[^>]*)>(?P<content>.*?)</style>",
    re.DOTALL,
)
_SETUP_ATTR_RE = re.compile(r"\bsetup\b")
_LANG_ATTR_RE = re.compile(r"""\blang\s*=\s*['"](?P<lang>[^'"]*)['"]""")

# ── Composition API patterns ──────────────────────────────────
_DEFINE_COMPONENT_RE = re.compile(r"\bdefineComponent\s*\(")
_DEFINE_PROPS_RE = re.compile(r"\bdefineProps\s*[<(]")
_DEFINE_EMITS_RE = re.compile(r"\bdefineEmits\s*[<(]")
_DEFINE_EXPOSE_RE = re.compile(r"\bdefineExpose\s*\(")
_DEFINE_SLOTS_RE = re.compile(r"\bdefineSlots\s*[<(]")
_DEFINE_MODEL_RE = re.compile(r"\bdefineModel\s*[<(]")

# Composition API reactivity
_REF_RE = re.compile(r"\bref\s*[<(]")
_REACTIVE_RE = re.compile(r"\breactive\s*[<(]")
_COMPUTED_RE = re.compile(r"\bcomputed\s*[<(]")
_WATCH_RE = re.compile(r"\bwatch\s*\(")
_WATCH_EFFECT_RE = re.compile(r"\bwatchEffect\s*\(")

# Composition API lifecycle hooks
_LIFECYCLE_HOOKS_RE = re.compile(
    r"\b(?P<hook>onMounted|onUnmounted|onBeforeMount|onBeforeUnmount"
    r"|onUpdated|onBeforeUpdate|onActivated|onDeactivated"
    r"|onErrorCaptured|onRenderTracked|onRenderTriggered"
    r"|onServerPrefetch)\s*\(",
)

# ── Options API patterns ──────────────────────────────────────
_OPTIONS_DATA_RE = re.compile(r"\bdata\s*\(\s*\)\s*\{")
_OPTIONS_METHODS_RE = re.compile(r"\bmethods\s*:\s*\{")
_OPTIONS_COMPUTED_RE = re.compile(r"\bcomputed\s*:\s*\{")
_OPTIONS_WATCH_RE = re.compile(r"\bwatch\s*:\s*\{")
_OPTIONS_LIFECYCLE_RE = re.compile(
    r"\b(?P<hook>mounted|unmounted|beforeMount|beforeUnmount"
    r"|updated|beforeUpdate|created|beforeCreate"
    r"|activated|deactivated|errorCaptured)\s*\(\s*\)",
)

# ── State management patterns ─────────────────────────────────
_VUEX_STORE_RE = re.compile(r"\b(?:createStore|useStore|mapState|mapGetters|mapActions|mapMutations)\s*\(")
_PINIA_STORE_RE = re.compile(r"\b(?:defineStore|useStore|storeToRefs)\s*\(")
_USE_STORE_RE = re.compile(r"\buse(?P<name>[A-Z][a-zA-Z0-9]*)Store\s*\(")

# ── Component registration ────────────────────────────────────
_COMPONENTS_OPTION_RE = re.compile(r"\bcomponents\s*:\s*\{")


class VueDetector(FrameworkDetector):
    """Detect Vue.js framework patterns in JavaScript/TypeScript projects."""

    @property
    def framework_name(self) -> str:
        return "vue"

    def detect_framework(self, project_root: str) -> bool:
        """Check package.json for vue dependency."""
        pkg_json = os.path.join(project_root, "package.json")
        if not os.path.isfile(pkg_json):
            return False

        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            return "vue" in deps or "vue" in dev_deps
        except (json.JSONDecodeError, OSError):
            return False

    def detect(
        self,
        file_path: str,
        tree: Any,
        source: bytes,
        nodes: list[Node],
        edges: list[Edge],
    ) -> list[FrameworkPattern]:
        """Detect per-file Vue patterns from source code.

        Identifies:
        - Single File Components (.vue files)
        - Composition API usage (defineComponent, defineProps, ref, etc.)
        - Options API usage (data, methods, computed, watch, lifecycle)
        - Vuex/Pinia store usage
        - Component registration
        """
        patterns: list[FrameworkPattern] = []
        source_text = source.decode("utf-8", errors="replace")

        is_vue_file = file_path.endswith(".vue")

        # ── SFC detection ─────────────────────────────────────
        if is_vue_file:
            sfc_pattern = self._detect_sfc(
                file_path, source_text, nodes,
            )
            if sfc_pattern:
                patterns.append(sfc_pattern)

        # ── Composition API detection ─────────────────────────
        composition_pattern = self._detect_composition_api(
            file_path, nodes, source_text,
        )
        if composition_pattern:
            patterns.append(composition_pattern)

        # ── Options API detection ─────────────────────────────
        options_pattern = self._detect_options_api(
            file_path, nodes, source_text,
        )
        if options_pattern:
            patterns.append(options_pattern)

        # ── Store detection ───────────────────────────────────
        store_pattern = self._detect_stores(
            file_path, nodes, source_text,
        )
        if store_pattern:
            patterns.append(store_pattern)

        return patterns

    def detect_global_patterns(self, store: Any) -> list[FrameworkPattern]:
        """Detect cross-file Vue patterns.

        Currently returns empty — Vue patterns are primarily per-file.
        Future: could detect component registration trees, store module composition.
        """
        return []

    # ── Private helpers ───────────────────────────────────────

    def _detect_sfc(
        self,
        file_path: str,
        source_text: str,
        nodes: list[Node],
    ) -> FrameworkPattern | None:
        """Detect Vue Single File Component structure.

        Identifies <template>, <script>, and <style> blocks,
        and creates a COMPONENT node for the SFC.
        """
        has_template = bool(_TEMPLATE_BLOCK_RE.search(source_text))
        has_script = bool(_SCRIPT_BLOCK_RE.search(source_text))
        has_style = bool(_STYLE_BLOCK_RE.search(source_text))

        if not has_template and not has_script:
            return None

        # Determine script setup and language
        script_match = _SCRIPT_BLOCK_RE.search(source_text)
        is_setup = False
        script_lang = "javascript"
        if script_match:
            attrs = script_match.group("attrs")
            is_setup = bool(_SETUP_ATTR_RE.search(attrs))
            lang_match = _LANG_ATTR_RE.search(attrs)
            if lang_match:
                lang = lang_match.group("lang")
                if lang in ("ts", "typescript"):
                    script_lang = "typescript"

        # Derive component name from file path
        component_name = self._component_name_from_path(file_path)

        new_nodes: list[Node] = []
        new_edges: list[Edge] = []

        component_node = Node(
            id=generate_node_id(file_path, 1, NodeKind.COMPONENT, component_name),
            kind=NodeKind.COMPONENT,
            name=component_name,
            qualified_name=component_name,
            file_path=file_path,
            start_line=1,
            end_line=source_text.count("\n") + 1,
            language=script_lang,
            metadata={
                "framework": "vue",
                "component_type": "sfc",
                "has_template": has_template,
                "has_script": has_script,
                "has_style": has_style,
                "script_setup": is_setup,
                "script_lang": script_lang,
            },
        )
        new_nodes.append(component_node)

        # Link to any function/class nodes in the file
        for n in nodes:
            if n.kind in (NodeKind.FUNCTION, NodeKind.CLASS, NodeKind.VARIABLE):
                new_edges.append(Edge(
                    source_id=component_node.id,
                    target_id=n.id,
                    kind=EdgeKind.CONTAINS,
                    confidence=0.90,
                    metadata={"framework": "vue"},
                ))

        return FrameworkPattern(
            framework_name="vue",
            pattern_type="sfc",
            nodes=new_nodes,
            edges=new_edges,
            metadata={
                "component_name": component_name,
                "has_template": has_template,
                "has_script": has_script,
                "has_style": has_style,
                "script_setup": is_setup,
            },
        )

    def _detect_composition_api(
        self,
        file_path: str,
        nodes: list[Node],
        source_text: str,
    ) -> FrameworkPattern | None:
        """Detect Vue Composition API patterns.

        Identifies defineComponent, defineProps, defineEmits, defineExpose,
        ref, reactive, computed, watch, and lifecycle hooks.
        """
        new_nodes: list[Node] = []
        new_edges: list[Edge] = []
        api_usages: list[str] = []

        # Check for defineComponent
        if _DEFINE_COMPONENT_RE.search(source_text):
            api_usages.append("defineComponent")

        # Check for script setup macros
        for name, regex in [
            ("defineProps", _DEFINE_PROPS_RE),
            ("defineEmits", _DEFINE_EMITS_RE),
            ("defineExpose", _DEFINE_EXPOSE_RE),
            ("defineSlots", _DEFINE_SLOTS_RE),
            ("defineModel", _DEFINE_MODEL_RE),
        ]:
            if regex.search(source_text):
                api_usages.append(name)

        # Check for reactivity primitives
        for name, regex in [
            ("ref", _REF_RE),
            ("reactive", _REACTIVE_RE),
            ("computed", _COMPUTED_RE),
            ("watch", _WATCH_RE),
            ("watchEffect", _WATCH_EFFECT_RE),
        ]:
            if regex.search(source_text):
                api_usages.append(name)

        # Check for lifecycle hooks
        for match in _LIFECYCLE_HOOKS_RE.finditer(source_text):
            hook_name = match.group("hook")
            if hook_name not in api_usages:
                api_usages.append(hook_name)

            line_no = source_text[:match.start()].count("\n") + 1
            hook_node = Node(
                id=generate_node_id(file_path, line_no, NodeKind.HOOK, hook_name),
                kind=NodeKind.HOOK,
                name=hook_name,
                qualified_name=f"vue:{hook_name}",
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                language="javascript",
                metadata={
                    "framework": "vue",
                    "hook_type": "lifecycle",
                    "api_style": "composition",
                },
            )
            new_nodes.append(hook_node)

            # Link hook to enclosing function
            enclosing = self._find_enclosing_function(line_no, nodes)
            if enclosing:
                new_edges.append(Edge(
                    source_id=enclosing.id,
                    target_id=hook_node.id,
                    kind=EdgeKind.USES_HOOK,
                    confidence=0.85,
                    line_number=line_no,
                    metadata={"framework": "vue", "hook_name": hook_name},
                ))

        if not api_usages:
            return None

        return FrameworkPattern(
            framework_name="vue",
            pattern_type="composition_api",
            nodes=new_nodes,
            edges=new_edges,
            metadata={
                "api_usages": api_usages,
                "usage_count": len(api_usages),
            },
        )

    def _detect_options_api(
        self,
        file_path: str,
        nodes: list[Node],
        source_text: str,
    ) -> FrameworkPattern | None:
        """Detect Vue Options API patterns.

        Identifies data(), methods, computed, watch, and lifecycle hooks.
        """
        options_found: list[str] = []
        new_nodes: list[Node] = []
        new_edges: list[Edge] = []

        for name, regex in [
            ("data", _OPTIONS_DATA_RE),
            ("methods", _OPTIONS_METHODS_RE),
            ("computed", _OPTIONS_COMPUTED_RE),
            ("watch", _OPTIONS_WATCH_RE),
        ]:
            if regex.search(source_text):
                options_found.append(name)

        # Check for Options API lifecycle hooks
        for match in _OPTIONS_LIFECYCLE_RE.finditer(source_text):
            hook_name = match.group("hook")
            if hook_name not in options_found:
                options_found.append(hook_name)

            line_no = source_text[:match.start()].count("\n") + 1
            hook_node = Node(
                id=generate_node_id(file_path, line_no, NodeKind.HOOK, hook_name),
                kind=NodeKind.HOOK,
                name=hook_name,
                qualified_name=f"vue:options:{hook_name}",
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                language="javascript",
                metadata={
                    "framework": "vue",
                    "hook_type": "lifecycle",
                    "api_style": "options",
                },
            )
            new_nodes.append(hook_node)

        if not options_found:
            return None

        return FrameworkPattern(
            framework_name="vue",
            pattern_type="options_api",
            nodes=new_nodes,
            edges=new_edges,
            metadata={
                "options_found": options_found,
                "option_count": len(options_found),
            },
        )

    def _detect_stores(
        self,
        file_path: str,
        nodes: list[Node],
        source_text: str,
    ) -> FrameworkPattern | None:
        """Detect Vuex and Pinia store usage."""
        new_nodes: list[Node] = []
        new_edges: list[Edge] = []
        store_usages: list[dict[str, str]] = []

        # Detect Pinia defineStore
        define_store_re = re.compile(
            r"""\bdefineStore\s*\(\s*['"](?P<name>[^'"]*)['"]"""
        )
        for match in define_store_re.finditer(source_text):
            store_name = match.group("name")
            line_no = source_text[:match.start()].count("\n") + 1
            store_usages.append({"type": "pinia", "name": store_name, "action": "define"})

            store_node = Node(
                id=generate_node_id(file_path, line_no, NodeKind.MODULE, f"store:{store_name}"),
                kind=NodeKind.MODULE,
                name=store_name,
                qualified_name=f"pinia:store:{store_name}",
                file_path=file_path,
                start_line=line_no,
                end_line=line_no,
                language="javascript",
                metadata={
                    "framework": "vue",
                    "store_type": "pinia",
                    "store_name": store_name,
                },
            )
            new_nodes.append(store_node)

        # Detect useXxxStore() calls (Pinia convention)
        for match in _USE_STORE_RE.finditer(source_text):
            store_name = match.group("name")
            line_no = source_text[:match.start()].count("\n") + 1
            store_usages.append({"type": "pinia", "name": store_name, "action": "use"})

            # Link to enclosing function
            enclosing = self._find_enclosing_function(line_no, nodes)
            if enclosing:
                new_edges.append(Edge(
                    source_id=enclosing.id,
                    target_id=f"__unresolved__:store:{store_name}",
                    kind=EdgeKind.CALLS,
                    confidence=0.80,
                    line_number=line_no,
                    metadata={
                        "framework": "vue",
                        "store_type": "pinia",
                        "store_name": store_name,
                    },
                ))

        # Detect Vuex patterns
        if _VUEX_STORE_RE.search(source_text):
            store_usages.append({"type": "vuex", "name": "vuex", "action": "use"})

        if not store_usages:
            return None

        return FrameworkPattern(
            framework_name="vue",
            pattern_type="stores",
            nodes=new_nodes,
            edges=new_edges,
            metadata={
                "store_usages": store_usages,
                "store_count": len(store_usages),
            },
        )

    # ── Utility helpers ───────────────────────────────────────

    @staticmethod
    def _component_name_from_path(file_path: str) -> str:
        """Derive a PascalCase component name from a file path.

        Examples:
            src/components/UserProfile.vue -> UserProfile
            src/components/user-profile.vue -> UserProfile
        """
        from pathlib import PurePosixPath
        stem = PurePosixPath(file_path.replace(os.sep, "/")).stem
        # Convert kebab-case to PascalCase
        parts = stem.replace("_", "-").split("-")
        return "".join(part[0].upper() + part[1:] if part else part for part in parts)

    @staticmethod
    def _find_enclosing_function(
        line_no: int, nodes: list[Node],
    ) -> Node | None:
        """Find the function/component that encloses a given line."""
        candidates = [
            n for n in nodes
            if n.kind in (NodeKind.FUNCTION, NodeKind.METHOD, NodeKind.VARIABLE)
            and n.start_line is not None
            and n.end_line is not None
            and n.start_line <= line_no <= n.end_line
        ]
        if not candidates:
            return None
        # Return the most specific (smallest range) enclosing function
        return min(
            candidates,
            key=lambda n: (n.end_line or 0) - (n.start_line or 0),
        )
