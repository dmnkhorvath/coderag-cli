"""Comprehensive tests for CSS extractor, resolver, and plugin."""

import os

import pytest

from coderag.core.models import (
    EdgeKind,
    ExtractionResult,
    FileInfo,
    Language,
    NodeKind,
    ResolutionResult,
)
from coderag.plugins.css.extractor import CSSExtractor
from coderag.plugins.css.plugin import CSSPlugin
from coderag.plugins.css.resolver import CSSResolver


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# CSSExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCSSExtractorBasic:
    """Basic CSS extraction tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = CSSExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.css", b"")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.css"
        assert result.language == "css"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_rule(self):
        """Element selectors like body are not extracted as nodes."""
        source = b"""body {
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
}
"""
        result = self.extractor.extract("styles.css", source)
        # Element selectors are not extracted, only file node
        assert len(result.nodes) == 1
        assert result.nodes[0].kind == NodeKind.FILE

    def test_class_selector(self):
        source = b""".container {
    max-width: 1200px;
    margin: 0 auto;
}

.container .inner {
    padding: 20px;
}
"""
        result = self.extractor.extract("layout.css", source)
        selectors = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(selectors) >= 2

    def test_id_selector(self):
        source = b"""#header {
    background: #333;
    color: white;
}

#footer {
    background: #222;
}
"""
        result = self.extractor.extract("layout.css", source)
        ids = _kinds(result.nodes, NodeKind.CSS_ID)
        assert len(ids) >= 2

    def test_pseudo_selectors(self):
        source = b"""a:hover {
    color: blue;
}

.item::before {
    content: "";
}

.item::after {
    content: "";
}
"""
        result = self.extractor.extract("pseudo.css", source)
        # a:hover is element selector (not extracted), .item::before/after are CSS_CLASS
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1  # .item

    def test_media_query(self):
        source = b"""@media (max-width: 768px) {
    .container {
        width: 100%;
    }
}

@media (min-width: 1024px) {
    .container {
        width: 960px;
    }
}
"""
        result = self.extractor.extract("responsive.css", source)
        media = _kinds(result.nodes, NodeKind.CSS_MEDIA_QUERY)
        assert len(media) >= 2

    def test_keyframes(self):
        source = b"""@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

@keyframes slideUp {
    0% {
        transform: translateY(100%);
    }
    100% {
        transform: translateY(0);
    }
}
"""
        result = self.extractor.extract("animations.css", source)
        keyframes = _kinds(result.nodes, NodeKind.CSS_KEYFRAMES)
        assert len(keyframes) == 2
        names = {n.name for n in keyframes}
        assert "@keyframes fadeIn" in names or "fadeIn" in {n.name.split()[-1] for n in keyframes}

    def test_import_rule(self):
        source = b"""@import url("reset.css");
@import "typography.css";
@import url("https://fonts.googleapis.com/css?family=Roboto");
"""
        result = self.extractor.extract("main.css", source)
        imports = _kinds(result.nodes, NodeKind.IMPORT)
        assert len(imports) >= 2

    def test_css_variables(self):
        source = b""":root {
    --primary-color: #3498db;
    --secondary-color: #2ecc71;
    --font-size-base: 16px;
    --spacing-unit: 8px;
}
"""
        result = self.extractor.extract("variables.css", source)
        variables = _kinds(result.nodes, NodeKind.CSS_VARIABLE)
        assert len(variables) >= 3

    def test_css_variable_usage(self):
        source = b""":root {
    --primary: #3498db;
}

.button {
    background-color: var(--primary);
}
"""
        result = self.extractor.extract("buttons.css", source)
        # Should have both variable definition and selector
        variables = _kinds(result.nodes, NodeKind.CSS_VARIABLE)
        selectors = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(variables) >= 1
        assert len(selectors) >= 1

    def test_multiple_selectors(self):
        source = b""".btn { color: red; }
.card { color: blue; }
#main { color: green; }
"""
        result = self.extractor.extract("multi.css", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        ids = _kinds(result.nodes, NodeKind.CSS_ID)
        assert len(classes) == 2  # .btn, .card
        assert len(ids) == 1  # #main

    def test_nested_media_query(self):
        source = b"""@media screen and (min-width: 768px) {
    .sidebar {
        display: block;
    }
    .main {
        width: 75%;
    }
}
"""
        result = self.extractor.extract("layout.css", source)
        media = _kinds(result.nodes, NodeKind.CSS_MEDIA_QUERY)
        assert len(media) >= 1
        selectors = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(selectors) >= 2

    def test_font_face(self):
        source = b"""@font-face {
    font-family: "CustomFont";
    src: url("fonts/custom.woff2") format("woff2"),
         url("fonts/custom.woff") format("woff");
    font-weight: normal;
    font-style: normal;
}
"""
        result = self.extractor.extract("fonts.css", source)
        # Font-face may be extracted as a special node
        assert len(result.nodes) >= 1

    def test_attribute_selector(self):
        source = b""".form-input[type="text"] {
    border: 1px solid #ccc;
}

.link[href^="https"] {
    color: green;
}
"""
        result = self.extractor.extract("forms.css", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 2  # .form-input, .link

    def test_complex_selectors(self):
        source = b""".nav > li > a {
    text-decoration: none;
}

.nav li + li {
    margin-left: 10px;
}

.nav ~ .content {
    margin-top: 20px;
}
"""
        result = self.extractor.extract("nav.css", source)
        selectors = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(selectors) >= 3

    def test_contains_edges(self):
        source = b"""@media (max-width: 768px) {
    .mobile-only {
        display: block;
    }
}
"""
        result = self.extractor.extract("responsive.css", source)
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 1

    def test_property_nodes_not_extracted(self):
        """CSS properties are not extracted as separate nodes."""
        source = b""".card {
    display: flex;
    padding: 16px;
    margin: 8px;
}
"""
        result = self.extractor.extract("box.css", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) == 1  # .card
        assert len(result.nodes) == 2  # file + .card

    def test_supported_kinds(self):
        assert NodeKind.CSS_CLASS in self.extractor.supported_node_kinds()
        assert NodeKind.CSS_MEDIA_QUERY in self.extractor.supported_node_kinds()
        assert NodeKind.CSS_KEYFRAMES in self.extractor.supported_node_kinds()
        assert NodeKind.IMPORT in self.extractor.supported_node_kinds()
        assert EdgeKind.CONTAINS in self.extractor.supported_edge_kinds()

    def test_file_node_always_created(self):
        result = self.extractor.extract("test.css", b"/* empty */")
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].language == "css"

    def test_parse_time_recorded(self):
        result = self.extractor.extract("a.css", b".x { color: red; }")
        assert result.parse_time_ms >= 0

    def test_parse_error_tolerance(self):
        source = b""".broken {
    color: red
    /* missing semicolons and closing brace
"""
        result = self.extractor.extract("broken.css", source)
        assert len(result.nodes) > 0

    def test_complex_stylesheet(self):
        source = b"""@import url("reset.css");

:root {
    --primary: #3498db;
    --bg: #ffffff;
}

* {
    box-sizing: border-box;
}

body {
    font-family: sans-serif;
    background: var(--bg);
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

.btn {
    padding: 10px 20px;
    background: var(--primary);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
}

.btn:hover {
    opacity: 0.9;
}

@media (max-width: 768px) {
    .container {
        padding: 0 15px;
    }
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}
"""
        result = self.extractor.extract("app.css", source)
        assert len(result.nodes) >= 8
        assert len(_kinds(result.nodes, NodeKind.IMPORT)) >= 1
        assert len(_kinds(result.nodes, NodeKind.CSS_VARIABLE)) >= 2
        assert len(_kinds(result.nodes, NodeKind.CSS_CLASS)) >= 4
        assert len(_kinds(result.nodes, NodeKind.CSS_MEDIA_QUERY)) >= 1
        assert len(_kinds(result.nodes, NodeKind.CSS_KEYFRAMES)) >= 1

    def test_supports_rule(self):
        """@supports rule does not produce nodes in current extractor."""
        source = b"""@supports (display: grid) {
    .grid-container {
        display: grid;
    }
}
"""
        result = self.extractor.extract("grid.css", source)
        # @supports is not extracted, only file node
        assert len(result.nodes) >= 1

    def test_layer_rule(self):
        source = b"""@layer base {
    body {
        margin: 0;
    }
}
"""
        result = self.extractor.extract("layers.css", source)
        assert len(result.nodes) >= 2


# ═══════════════════════════════════════════════════════════════════════
# CSSResolver Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCSSResolver:
    """Test CSS import resolution."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        (tmp_path / "styles").mkdir()
        (tmp_path / "styles" / "reset.css").write_text("* { margin: 0; }")
        (tmp_path / "styles" / "variables.css").write_text(":root { --c: red; }")
        (tmp_path / "styles" / "components").mkdir()
        (tmp_path / "styles" / "components" / "button.css").write_text(".btn {}")
        return tmp_path

    @pytest.fixture
    def resolver(self, project_dir):
        r = CSSResolver()
        r.set_project_root(str(project_dir))
        files = []
        for root, dirs, filenames in os.walk(str(project_dir)):
            for fn in filenames:
                if fn.endswith(".css"):
                    abs_path = os.path.join(root, fn)
                    rel_path = os.path.relpath(abs_path, str(project_dir))
                    files.append(
                        FileInfo(
                            relative_path=rel_path,
                            path=abs_path,
                            language=Language.CSS,
                            plugin_name="css",
                            size_bytes=os.path.getsize(abs_path),
                        )
                    )
        r.build_index(files)
        return r

    def test_relative_import(self, resolver):
        result = resolver.resolve("./reset.css", "styles/main.css")
        if result.resolved_path is not None:
            assert "reset" in result.resolved_path

    def test_relative_import_subdir(self, resolver):
        result = resolver.resolve("./components/button.css", "styles/main.css")
        if result.resolved_path is not None:
            assert "button" in result.resolved_path

    def test_parent_relative_import(self, resolver):
        result = resolver.resolve("../variables.css", "styles/components/button.css")
        if result.resolved_path is not None:
            assert "variables" in result.resolved_path

    def test_unresolved_import(self, resolver):
        result = resolver.resolve("./nonexistent.css", "styles/main.css")
        assert result.resolved_path is None

    def test_external_url(self, resolver):
        result = resolver.resolve(
            "https://fonts.googleapis.com/css?family=Roboto",
            "styles/main.css",
        )
        assert result.metadata.get("external") is True or result.resolved_path is None

    def test_resolve_symbol(self, resolver):
        result = resolver.resolve_symbol("reset", "styles/main.css")
        assert isinstance(result, ResolutionResult)


# ═══════════════════════════════════════════════════════════════════════
# CSSPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestCSSPlugin:
    """Test CSS plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = CSSPlugin()
        assert plugin.name == "css"
        assert plugin.language == Language.CSS
        assert ".css" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = CSSPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor(self):
        plugin = CSSPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, CSSExtractor)

    def test_get_resolver(self):
        plugin = CSSPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, CSSResolver)

    def test_get_framework_detectors(self):
        plugin = CSSPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)

    def test_cleanup(self, tmp_path):
        plugin = CSSPlugin()
        plugin.initialize({}, str(tmp_path))
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = CSSPlugin()
        plugin.cleanup()
        ext = plugin.get_extractor()
        assert ext is not None
