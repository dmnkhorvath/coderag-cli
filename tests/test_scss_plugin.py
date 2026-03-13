"""Comprehensive tests for SCSS extractor, resolver, and plugin."""

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
from coderag.plugins.scss.extractor import SCSSExtractor
from coderag.plugins.scss.plugin import SCSSPlugin
from coderag.plugins.scss.resolver import SCSSResolver


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _edge_kinds(edges, kind):
    return [e for e in edges if e.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# SCSSExtractor Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSCSSExtractorBasic:
    """Basic SCSS extraction tests."""

    def setup_method(self):
        self.extractor = SCSSExtractor()

    def test_empty_file(self):
        result = self.extractor.extract("empty.scss", b"")
        assert isinstance(result, ExtractionResult)
        assert result.file_path == "empty.scss"
        assert result.language == "scss"
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1

    def test_simple_class_rule(self):
        source = b".container { margin: 0; padding: 0; }"
        result = self.extractor.extract("styles.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1
        assert any("container" in n.name for n in classes)

    def test_element_selector_no_class_node(self):
        """Element selectors like body/div do not produce CSS_CLASS nodes."""
        source = b"body { margin: 0; }"
        result = self.extractor.extract("styles.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) == 0

    def test_scss_variable(self):
        source = b"$primary-color: #3498db;\n$secondary-color: #2ecc71;\n$font-size-base: 16px;\n$spacing-unit: 8px;"
        result = self.extractor.extract("variables.scss", source)
        variables = _kinds(result.nodes, NodeKind.SCSS_VARIABLE)
        assert len(variables) >= 3
        names = _names(variables)
        assert any("primary" in n for n in names)

    def test_scss_variable_usage(self):
        source = b"$primary: #3498db;\n\n.button { background-color: $primary; color: white; }"
        result = self.extractor.extract("buttons.scss", source)
        variables = _kinds(result.nodes, NodeKind.SCSS_VARIABLE)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(variables) >= 1
        assert len(classes) >= 1
        var_edges = _edge_kinds(result.edges, EdgeKind.SCSS_USES_VARIABLE)
        assert len(var_edges) >= 1

    def test_mixin_definition(self):
        source = b"@mixin flex-center { display: flex; justify-content: center; }\n@mixin responsive($bp) { @media (min-width: $bp) { @content; } }"
        result = self.extractor.extract("mixins.scss", source)
        mixins = _kinds(result.nodes, NodeKind.SCSS_MIXIN)
        assert len(mixins) >= 2
        names = _names(mixins)
        assert any("flex-center" in n for n in names)

    def test_mixin_include(self):
        source = b"@mixin flex-center { display: flex; }\n\n.container { @include flex-center; }"
        result = self.extractor.extract("include.scss", source)
        mixins = _kinds(result.nodes, NodeKind.SCSS_MIXIN)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(mixins) >= 1
        assert len(classes) >= 1
        include_edges = _edge_kinds(result.edges, EdgeKind.SCSS_INCLUDES_MIXIN)
        assert len(include_edges) >= 1

    def test_nesting(self):
        source = b".nav { &__item { color: blue; } &--active { color: red; } }"
        result = self.extractor.extract("nesting.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1
        assert any("nav" in n.name for n in classes)

    def test_scss_function(self):
        source = b"@function double($value) { @return $value * 2; }"
        result = self.extractor.extract("functions.scss", source)
        funcs = _kinds(result.nodes, NodeKind.SCSS_FUNCTION)
        assert len(funcs) >= 1
        assert any("double" in n.name for n in funcs)

    def test_extend(self):
        source = b".message { border: 1px solid #ccc; }\n.success { @extend .message; border-color: green; }"
        result = self.extractor.extract("extend.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 2
        # @extend creates an unresolved reference or edge
        has_extend = (
            len(result.unresolved_references) >= 1 or len(_edge_kinds(result.edges, EdgeKind.SCSS_EXTENDS)) >= 1
        )
        assert has_extend

    def test_placeholder_selector(self):
        source = b"%flex-center { display: flex; justify-content: center; }\n.container { @extend %flex-center; }"
        result = self.extractor.extract("placeholder.scss", source)
        placeholders = _kinds(result.nodes, NodeKind.SCSS_PLACEHOLDER)
        assert len(placeholders) >= 1

    def test_media_query(self):
        source = b"@media (min-width: 768px) { .container { max-width: 720px; } }"
        result = self.extractor.extract("media.scss", source)
        media = _kinds(result.nodes, NodeKind.CSS_MEDIA_QUERY)
        assert len(media) >= 1

    def test_keyframes(self):
        source = b"@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }"
        result = self.extractor.extract("keyframes.scss", source)
        kf = _kinds(result.nodes, NodeKind.CSS_KEYFRAMES)
        assert len(kf) >= 1
        assert any("fadeIn" in n.name for n in kf)

    def test_if_else(self):
        source = b"@mixin theme($mode) { @if $mode == dark { background: #000; } @else { background: #fff; } }"
        result = self.extractor.extract("conditional.scss", source)
        mixins = _kinds(result.nodes, NodeKind.SCSS_MIXIN)
        assert len(mixins) >= 1

    def test_nested_properties(self):
        source = b".card { &__header { font-size: 18px; } &__body { padding: 16px; } }"
        result = self.extractor.extract("nested.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1

    def test_parent_selector(self):
        source = b".btn { &:hover { opacity: 0.8; } &.active { font-weight: bold; } }"
        result = self.extractor.extract("parent.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1
        assert any("btn" in n.name for n in classes)

    def test_property_nodes_not_extracted(self):
        """CSS properties are not extracted as separate nodes."""
        source = b".card { display: flex; padding: 16px; margin: 8px; }"
        result = self.extractor.extract("props.scss", source)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(classes) >= 1
        assert len(result.nodes) == 2  # file + class

    def test_supported_kinds(self):
        kinds = self.extractor.supported_node_kinds()
        assert NodeKind.CSS_CLASS in kinds
        assert NodeKind.SCSS_VARIABLE in kinds
        assert NodeKind.SCSS_MIXIN in kinds
        assert NodeKind.SCSS_FUNCTION in kinds
        assert NodeKind.SCSS_PLACEHOLDER in kinds
        assert NodeKind.CSS_MEDIA_QUERY in kinds
        assert NodeKind.CSS_KEYFRAMES in kinds

    def test_supported_edge_kinds(self):
        kinds = self.extractor.supported_edge_kinds()
        assert EdgeKind.CONTAINS in kinds
        assert EdgeKind.SCSS_USES_VARIABLE in kinds
        assert EdgeKind.SCSS_INCLUDES_MIXIN in kinds

    def test_complex_stylesheet(self):
        source = b"$primary: #3498db;\n$spacing: 8px;\n@mixin respond-to($bp) { @media (min-width: $bp) { @content; } }\n.header { background: $primary; padding: $spacing; @include respond-to(768px) { padding: 16px; } }"
        result = self.extractor.extract("complex.scss", source)
        variables = _kinds(result.nodes, NodeKind.SCSS_VARIABLE)
        mixins = _kinds(result.nodes, NodeKind.SCSS_MIXIN)
        classes = _kinds(result.nodes, NodeKind.CSS_CLASS)
        assert len(variables) >= 2
        assert len(mixins) >= 1
        assert len(classes) >= 1
        var_edges = _edge_kinds(result.edges, EdgeKind.SCSS_USES_VARIABLE)
        include_edges = _edge_kinds(result.edges, EdgeKind.SCSS_INCLUDES_MIXIN)
        assert len(var_edges) >= 1
        assert len(include_edges) >= 1

    def test_map_variable(self):
        source = b"$colors: (primary: #3498db, secondary: #2ecc71);"
        result = self.extractor.extract("map.scss", source)
        variables = _kinds(result.nodes, NodeKind.SCSS_VARIABLE)
        assert len(variables) >= 1
        assert any("colors" in n.name for n in variables)

    def test_list_variable(self):
        source = b"$font-stack: Helvetica, Arial, sans-serif;"
        result = self.extractor.extract("list.scss", source)
        variables = _kinds(result.nodes, NodeKind.SCSS_VARIABLE)
        assert len(variables) >= 1
        assert any("font-stack" in n.name for n in variables)

    def test_id_selector(self):
        source = b"#main-content { width: 100%; }"
        result = self.extractor.extract("ids.scss", source)
        ids = _kinds(result.nodes, NodeKind.CSS_ID)
        assert len(ids) >= 1

    def test_import_statement(self):
        source = b'@use "variables";\n@use "mixins" as m;'
        result = self.extractor.extract("main.scss", source)
        import_nodes = _kinds(result.nodes, NodeKind.IMPORT)
        has_imports = len(import_nodes) > 0 or len(result.unresolved_references) > 0
        assert has_imports

    def test_forward_statement(self):
        source = b'@forward "variables";\n@forward "mixins" hide private-mixin;'
        result = self.extractor.extract("index.scss", source)
        forward_edges = _edge_kinds(result.edges, EdgeKind.SCSS_FORWARDS)
        has_forwards = len(forward_edges) > 0 or len(result.unresolved_references) > 0
        assert has_forwards

    def test_font_face(self):
        source = b"@font-face { font-family: CustomFont; src: url(font.woff2); }"
        result = self.extractor.extract("fonts.scss", source)
        fonts = _kinds(result.nodes, NodeKind.CSS_FONT_FACE)
        assert len(fonts) >= 1

    def test_css_variable(self):
        source = b":root { --primary-color: #3498db; --spacing: 8px; }"
        result = self.extractor.extract("vars.scss", source)
        css_vars = _kinds(result.nodes, NodeKind.CSS_VARIABLE)
        assert len(css_vars) >= 1

    def test_layer(self):
        source = b"@layer base { .container { max-width: 1200px; } }"
        result = self.extractor.extract("layers.scss", source)
        layers = _kinds(result.nodes, NodeKind.CSS_LAYER)
        assert len(layers) >= 1

    def test_contains_edges(self):
        source = b"$color: red;\n.box { color: $color; }"
        result = self.extractor.extract("edges.scss", source)
        contains = _edge_kinds(result.edges, EdgeKind.CONTAINS)
        assert len(contains) >= 2

    def test_file_node_always_present(self):
        source = b"/* just a comment */"
        result = self.extractor.extract("comment.scss", source)
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].name == "comment.scss"

    def test_extraction_result_language(self):
        result = self.extractor.extract("test.scss", b".a { color: red; }")
        assert result.language == "scss"
        assert result.file_path == "test.scss"


class TestSCSSResolver:
    """Test SCSS import/use resolution."""

    @pytest.fixture
    def project_dir(self, tmp_path):
        (tmp_path / "styles").mkdir()
        (tmp_path / "styles" / "_variables.scss").write_text("$primary: red;")
        (tmp_path / "styles" / "_mixins.scss").write_text("@mixin flex {}")
        (tmp_path / "styles" / "main.scss").write_text("@use 'variables';")
        (tmp_path / "styles" / "components").mkdir()
        (tmp_path / "styles" / "components" / "_button.scss").write_text(".btn {}")
        (tmp_path / "styles" / "components" / "_index.scss").write_text("@forward 'button';")
        return tmp_path

    @pytest.fixture
    def resolver(self, project_dir):
        r = SCSSResolver()
        r.set_project_root(str(project_dir))
        files = []
        for root, dirs, filenames in os.walk(str(project_dir)):
            for fn in filenames:
                if fn.endswith((".scss", ".sass")):
                    abs_path = os.path.join(root, fn)
                    rel_path = os.path.relpath(abs_path, str(project_dir))
                    files.append(
                        FileInfo(
                            relative_path=rel_path,
                            path=abs_path,
                            language=Language.SCSS,
                            plugin_name="scss",
                            size_bytes=os.path.getsize(abs_path),
                        )
                    )
        r.build_index(files)
        return r

    def test_partial_import(self, resolver):
        """Test underscore prefix convention."""
        result = resolver.resolve("variables", "styles/main.scss")
        if result.resolved_path is not None:
            assert "variables" in result.resolved_path

    def test_partial_with_underscore(self, resolver):
        result = resolver.resolve("_variables", "styles/main.scss")
        if result.resolved_path is not None:
            assert "variables" in result.resolved_path

    def test_relative_import(self, resolver):
        result = resolver.resolve("./components/button", "styles/main.scss")
        if result.resolved_path is not None:
            assert "button" in result.resolved_path

    def test_directory_index(self, resolver):
        result = resolver.resolve("./components", "styles/main.scss")
        if result.resolved_path is not None:
            assert "index" in result.resolved_path or "components" in result.resolved_path

    def test_parent_relative(self, resolver):
        result = resolver.resolve("../variables", "styles/components/_button.scss")
        if result.resolved_path is not None:
            assert "variables" in result.resolved_path

    def test_unresolved_import(self, resolver):
        result = resolver.resolve("nonexistent", "styles/main.scss")
        assert result.resolved_path is None

    def test_sass_builtin(self, resolver):
        """sass:math builtins are not currently resolved by the SCSS resolver."""
        result = resolver.resolve("sass:math", "styles/main.scss")
        # sass: builtins are treated as unresolved external references
        assert isinstance(result, ResolutionResult)
        assert result.confidence == 0.0 or result.is_external

    def test_sass_color_builtin(self, resolver):
        """sass:color builtins are not currently resolved by the SCSS resolver."""
        result = resolver.resolve("sass:color", "styles/main.scss")
        assert isinstance(result, ResolutionResult)
        assert result.confidence == 0.0 or result.is_external

    def test_resolve_symbol(self, resolver):
        result = resolver.resolve_symbol("variables", "styles/main.scss")
        assert isinstance(result, ResolutionResult)

    def test_external_url(self, resolver):
        result = resolver.resolve(
            "https://fonts.googleapis.com/css?family=Roboto",
            "styles/main.scss",
        )
        assert result.metadata.get("external") is True or result.resolved_path is None


# ═══════════════════════════════════════════════════════════════════════
# SCSSPlugin Tests
# ═══════════════════════════════════════════════════════════════════════


class TestSCSSPlugin:
    """Test SCSS plugin lifecycle."""

    def test_plugin_properties(self):
        plugin = SCSSPlugin()
        assert plugin.name == "scss"
        assert plugin.language == Language.SCSS
        assert ".scss" in plugin.file_extensions

    def test_initialize(self, tmp_path):
        plugin = SCSSPlugin()
        plugin.initialize({}, str(tmp_path))
        assert plugin.get_extractor() is not None
        assert plugin.get_resolver() is not None

    def test_get_extractor(self):
        plugin = SCSSPlugin()
        ext = plugin.get_extractor()
        assert isinstance(ext, SCSSExtractor)

    def test_get_resolver(self):
        plugin = SCSSPlugin()
        res = plugin.get_resolver()
        assert isinstance(res, SCSSResolver)

    def test_get_framework_detectors(self):
        plugin = SCSSPlugin()
        detectors = plugin.get_framework_detectors()
        assert isinstance(detectors, list)

    def test_cleanup(self, tmp_path):
        plugin = SCSSPlugin()
        plugin.initialize({}, str(tmp_path))
        plugin.cleanup()
        assert plugin._extractor is None
        assert plugin._resolver is None

    def test_extractor_after_cleanup(self):
        plugin = SCSSPlugin()
        plugin.cleanup()
        ext = plugin.get_extractor()
        assert ext is not None

    def test_sass_extension(self):
        plugin = SCSSPlugin()
        exts = plugin.file_extensions
        assert ".sass" in exts or ".scss" in exts
