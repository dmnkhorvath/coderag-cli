"""Tests for Vue SFC parsing (BUG #1) and placeholder language fix (BUG #2)."""

import pytest

from coderag.core.models import (
    EdgeKind,
    ExtractionResult,
    NodeKind,
    UnresolvedReference,
)
from coderag.plugins.typescript.extractor import TypeScriptExtractor
from coderag.plugins.typescript.plugin import TypeScriptPlugin


def _kinds(nodes, kind):
    return [n for n in nodes if n.kind == kind]


def _names(nodes):
    return [n.name for n in nodes]


# ═══════════════════════════════════════════════════════════════════════
# BUG #1: Vue SFC Parsing Tests
# ═══════════════════════════════════════════════════════════════════════


class TestVueSFCPlugin:
    """Test that .vue files are recognized by the TypeScript plugin."""

    def test_vue_in_file_extensions(self):
        plugin = TypeScriptPlugin()
        assert ".vue" in plugin.file_extensions

    def test_ts_extensions_still_present(self):
        plugin = TypeScriptPlugin()
        for ext in (".ts", ".tsx", ".mts", ".cts"):
            assert ext in plugin.file_extensions


class TestVueSFCExtraction:
    """Test Vue Single File Component script extraction and parsing."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.extractor = TypeScriptExtractor()

    def test_vue_basic_script_setup_ts(self):
        """Test parsing a Vue SFC with <script setup lang="ts">."""
        source = b"""<template>
  <div>{{ message }}</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const message = ref('Hello')

function greet(name: string): string {
  return `Hello, ${name}`
}
</script>

<style scoped>
.container { color: red; }
</style>
"""
        result = self.extractor.extract("components/Hello.vue", source)
        assert result.language == "typescript"
        assert result.file_path == "components/Hello.vue"

        # Should have FILE node
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].name == "Hello.vue"

        # Should have extracted the function
        functions = _kinds(result.nodes, NodeKind.FUNCTION)
        func_names = _names(functions)
        assert "greet" in func_names

        # const declarations are extracted as CONSTANT
        constants = _kinds(result.nodes, NodeKind.CONSTANT)
        const_names = _names(constants)
        assert "message" in const_names

    def test_vue_line_offset_correct(self):
        """Test that line numbers are offset correctly for Vue SFC."""
        source = b"""<template>
  <div>test</div>
</template>

<script setup lang="ts">
function hello(): void {
  console.log('hi')
}
</script>
"""
        result = self.extractor.extract("App.vue", source)
        functions = _kinds(result.nodes, NodeKind.FUNCTION)
        hello_funcs = [f for f in functions if f.name == "hello"]
        assert len(hello_funcs) == 1
        # "function hello()" is on line 6 of the .vue file (1-indexed)
        # Line 0: <template>, Line 1: <div>, Line 2: </template>,
        # Line 3: blank, Line 4: <script...>, Line 5: function hello()
        assert hello_funcs[0].start_line == 6

    def test_vue_script_without_lang(self):
        """Test parsing a Vue SFC with plain <script> (no lang attribute)."""
        source = b"""<template>
  <div>test</div>
</template>

<script>
export default {
  name: 'MyComponent',
  data() {
    return { count: 0 }
  }
}
</script>
"""
        result = self.extractor.extract("Plain.vue", source)
        assert result.language == "typescript"
        # Should still parse - TS parser handles JS
        assert len(result.nodes) >= 1  # At least FILE node

    def test_vue_script_lang_ts(self):
        """Test parsing a Vue SFC with <script lang="ts"> containing a class."""
        source = b"""<template>
  <div>test</div>
</template>

<script lang="ts">
export class MyService {
  greet(): string {
    return 'hello'
  }
}
</script>
"""
        result = self.extractor.extract("Typed.vue", source)
        assert result.language == "typescript"
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert "MyService" in _names(classes)

    def test_vue_no_script_block(self):
        """Test that a .vue file with no <script> block returns minimal result."""
        source = b"""<template>
  <div>Just a template</div>
</template>

<style>
.foo { color: red; }
</style>
"""
        result = self.extractor.extract("NoScript.vue", source)
        assert result.language == "typescript"
        # Should have only the FILE node
        assert len(result.nodes) == 1
        assert result.nodes[0].kind == NodeKind.FILE

    def test_vue_multiple_script_blocks_prefers_ts(self):
        """Test that when multiple script blocks exist, lang=ts is preferred."""
        source = b"""<template>
  <div>test</div>
</template>

<script>
// plain JS block
var x = 1
</script>

<script lang="ts">
interface User {
  name: string
  age: number
}
</script>
"""
        result = self.extractor.extract("Multi.vue", source)
        # Should prefer the lang="ts" block and find the interface
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        iface_names = _names(interfaces)
        assert "User" in iface_names

    def test_vue_script_setup_preferred_over_plain(self):
        """Test that <script setup> is preferred over plain <script>."""
        source = b"""<template>
  <div>test</div>
</template>

<script>
var legacy = 1
</script>

<script setup lang="ts">
const modern = ref(0)
</script>
"""
        result = self.extractor.extract("SetupPreferred.vue", source)
        # const declarations are extracted as CONSTANT
        constants = _kinds(result.nodes, NodeKind.CONSTANT)
        const_names = _names(constants)
        assert "modern" in const_names

    def test_vue_extract_helper_no_script(self):
        """Test _extract_vue_script returns empty for no script block."""
        source = b"<template><div>hi</div></template>"
        content, offset = TypeScriptExtractor._extract_vue_script(source)
        assert content == b""
        assert offset == 0

    def test_vue_extract_helper_with_script(self):
        """Test _extract_vue_script returns correct content and offset."""
        source = b"""<template>
  <div>hi</div>
</template>

<script setup lang="ts">
const x = 1
</script>
"""
        content, offset = TypeScriptExtractor._extract_vue_script(source)
        assert b"const x = 1" in content
        # <script> tag is on line 4 (0-indexed), so offset = 4
        assert offset == 4

    def test_vue_extract_skips_json_script(self):
        """Test that application/json script blocks are skipped."""
        source = b"""<template><div>hi</div></template>
<script type="application/json">{"key": "value"}</script>
<script lang="ts">
const x = 1
</script>
"""
        content, offset = TypeScriptExtractor._extract_vue_script(source)
        assert b"const x = 1" in content
        assert b"key" not in content

    def test_vue_class_extraction(self):
        """Test that classes in Vue SFC are extracted."""
        source = b"""<template>
  <div>test</div>
</template>

<script lang="ts">
export class UserService {
  private name: string

  constructor(name: string) {
    this.name = name
  }

  greet(): string {
    return `Hello, ${this.name}`
  }
}
</script>
"""
        result = self.extractor.extract("ClassComp.vue", source)
        classes = _kinds(result.nodes, NodeKind.CLASS)
        assert "UserService" in _names(classes)
        methods = _kinds(result.nodes, NodeKind.METHOD)
        method_names = _names(methods)
        assert "greet" in method_names
        assert "constructor" in method_names

    def test_vue_interface_extraction(self):
        """Test that interfaces in Vue SFC are extracted."""
        source = b"""<template><div>test</div></template>

<script setup lang="ts">
interface Props {
  title: string
  count: number
}

const props = defineProps<Props>()
</script>
"""
        result = self.extractor.extract("WithProps.vue", source)
        interfaces = _kinds(result.nodes, NodeKind.INTERFACE)
        assert "Props" in _names(interfaces)

    def test_vue_enum_extraction(self):
        """Test that enums in Vue SFC are extracted."""
        source = b"""<template><div>test</div></template>

<script setup lang="ts">
enum Status {
  Active = 'active',
  Inactive = 'inactive',
}
</script>
"""
        result = self.extractor.extract("WithEnum.vue", source)
        enums = _kinds(result.nodes, NodeKind.ENUM)
        assert "Status" in _names(enums)

    def test_vue_type_alias_extraction(self):
        """Test that type aliases in Vue SFC are extracted."""
        source = b"""<template><div>test</div></template>

<script setup lang="ts">
type UserID = string | number
</script>
"""
        result = self.extractor.extract("WithType.vue", source)
        type_aliases = _kinds(result.nodes, NodeKind.TYPE_ALIAS)
        assert "UserID" in _names(type_aliases)

    def test_vue_file_node_has_correct_lines(self):
        """Test that the FILE node spans the entire .vue file."""
        source = b"""<template>
  <div>test</div>
</template>

<script setup lang="ts">
const x = 1
</script>
"""
        result = self.extractor.extract("Span.vue", source)
        file_nodes = _kinds(result.nodes, NodeKind.FILE)
        assert len(file_nodes) == 1
        assert file_nodes[0].start_line == 1
        # File node should span the whole file
        assert file_nodes[0].end_line >= 7


# ═══════════════════════════════════════════════════════════════════════
# BUG #2: Placeholder Language Fix Tests
# ═══════════════════════════════════════════════════════════════════════


class TestPlaceholderLanguage:
    """Test that placeholder nodes get the correct language from source."""

    @pytest.fixture
    def store_with_nodes(self, tmp_path):
        """Create a SQLite store with some nodes for resolution."""
        from coderag.storage.sqlite_store import SQLiteStore

        db_path = tmp_path / "test.db"
        store = SQLiteStore(str(db_path))
        store.initialize()
        return store

    def test_placeholder_gets_typescript_language(self, store_with_nodes):
        """Test placeholder nodes get typescript language for TS files."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        ts_result = ExtractionResult(
            file_path="src/app.ts",
            language="typescript",
            unresolved_references=[
                UnresolvedReference(
                    source_node_id="src/app.ts:10:function:main",
                    reference_name="SomeExternalLib",
                    reference_kind=EdgeKind.IMPORTS,
                    line_number=10,
                )
            ],
        )

        edges, placeholders, resolved, unresolved = resolver.resolve([ts_result])
        assert len(placeholders) == 1
        assert placeholders[0].language == "typescript"
        assert placeholders[0].metadata.get("external") is True

    def test_placeholder_gets_python_language(self, store_with_nodes):
        """Test placeholder nodes get python language for Python files."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        py_result = ExtractionResult(
            file_path="src/main.py",
            language="python",
            unresolved_references=[
                UnresolvedReference(
                    source_node_id="src/main.py:5:class:App",
                    reference_name="flask.Flask",
                    reference_kind=EdgeKind.IMPORTS,
                    line_number=5,
                )
            ],
        )

        edges, placeholders, resolved, unresolved = resolver.resolve([py_result])
        assert len(placeholders) == 1
        assert placeholders[0].language == "python"

    def test_placeholder_gets_javascript_language(self, store_with_nodes):
        """Test placeholder nodes get javascript language for JS files."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        js_result = ExtractionResult(
            file_path="src/index.js",
            language="javascript",
            unresolved_references=[
                UnresolvedReference(
                    source_node_id="src/index.js:1:import:react",
                    reference_name="react",
                    reference_kind=EdgeKind.IMPORTS,
                    line_number=1,
                )
            ],
        )

        edges, placeholders, resolved, unresolved = resolver.resolve([js_result])
        assert len(placeholders) == 1
        assert placeholders[0].language == "javascript"

    def test_placeholder_gets_php_language_for_php(self, store_with_nodes):
        """Test placeholder nodes correctly get php language for PHP files."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        php_result = ExtractionResult(
            file_path="src/Controller.php",
            language="php",
            unresolved_references=[
                UnresolvedReference(
                    source_node_id="src/Controller.php:3:class:BaseController",
                    reference_name="Illuminate\\Http\\Request",
                    reference_kind=EdgeKind.IMPORTS,
                    line_number=3,
                )
            ],
        )

        edges, placeholders, resolved, unresolved = resolver.resolve([php_result])
        assert len(placeholders) == 1
        assert placeholders[0].language == "php"

    def test_placeholder_no_hardcoded_php(self, store_with_nodes):
        """Regression test: placeholder language must NOT be hardcoded to php."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        results = [
            ExtractionResult(
                file_path="src/app.ts",
                language="typescript",
                unresolved_references=[
                    UnresolvedReference(
                        source_node_id="src/app.ts:1:import:foo",
                        reference_name="ExternalTSLib",
                        reference_kind=EdgeKind.IMPORTS,
                        line_number=1,
                    )
                ],
            ),
            ExtractionResult(
                file_path="src/main.py",
                language="python",
                unresolved_references=[
                    UnresolvedReference(
                        source_node_id="src/main.py:1:import:bar",
                        reference_name="ExternalPyLib",
                        reference_kind=EdgeKind.IMPORTS,
                        line_number=1,
                    )
                ],
            ),
            ExtractionResult(
                file_path="src/index.js",
                language="javascript",
                unresolved_references=[
                    UnresolvedReference(
                        source_node_id="src/index.js:1:import:baz",
                        reference_name="ExternalJSLib",
                        reference_kind=EdgeKind.IMPORTS,
                        line_number=1,
                    )
                ],
            ),
        ]

        edges, placeholders, resolved, unresolved = resolver.resolve(results)
        assert len(placeholders) == 3

        languages = {p.language for p in placeholders}
        # None of them should be hardcoded to php
        assert languages == {"typescript", "python", "javascript"}

    def test_placeholder_default_language_for_unknown(self, store_with_nodes):
        """Test that _resolve_one defaults to 'unknown' when no language given."""
        from coderag.pipeline.resolver import ReferenceResolver

        resolver = ReferenceResolver(store_with_nodes)
        resolver.build_symbol_table()

        # Directly call _resolve_one without language (uses default)
        ref = UnresolvedReference(
            source_node_id="unknown:1:class:Foo",
            reference_name="NonExistentSymbol",
            reference_kind=EdgeKind.IMPORTS,
            line_number=1,
        )
        edge, placeholder = resolver._resolve_one(ref, set())
        assert placeholder is not None
        assert placeholder.language == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# detect_language tests for .vue
# ═══════════════════════════════════════════════════════════════════════


class TestDetectLanguageVue:
    """Test that detect_language recognizes .vue files."""

    def test_vue_detected_as_typescript(self):
        from coderag.core.models import detect_language

        assert detect_language("components/App.vue") == "typescript"

    def test_vue_nested_path(self):
        from coderag.core.models import detect_language

        assert detect_language("src/views/Home.vue") == "typescript"

    def test_existing_extensions_unchanged(self):
        from coderag.core.models import detect_language

        assert detect_language("app.ts") == "typescript"
        assert detect_language("app.tsx") == "typescript"
        assert detect_language("app.js") == "javascript"
        assert detect_language("app.php") == "php"
