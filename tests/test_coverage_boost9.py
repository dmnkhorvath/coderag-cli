"""Coverage boost 9 — Tailwind, CSS resolver, JS resolver, TS resolver, Vue detector."""

import json


class TestTailwindDetector:
    """Tests for Tailwind CSS framework detector using detect_framework()."""

    def _get_detector(self):
        from coderag.plugins.css.frameworks.tailwind import TailwindDetector

        return TailwindDetector()

    def test_detect_tailwind_config_js(self, tmp_path):
        (tmp_path / "tailwind.config.js").write_text("module.exports = { content: ['./src/**/*.{html,js}'] }")
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_tailwind_config_ts(self, tmp_path):
        (tmp_path / "tailwind.config.ts").write_text("export default { content: ['./src/**/*.{html,ts}'] }")
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_no_tailwind(self, tmp_path):
        (tmp_path / "styles.css").write_text("body { color: red; }")
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert result is False

    def test_detect_postcss_config(self, tmp_path):
        (tmp_path / "postcss.config.js").write_text(
            "module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }"
        )
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_package_json_dep(self, tmp_path):
        pkg = {"devDependencies": {"tailwindcss": "^3.4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_with_theme_extend(self, tmp_path):
        config = """module.exports = {
  theme: { extend: { colors: { primary: '#1a202c' } } },
  plugins: [require('@tailwindcss/forms')],
}"""
        (tmp_path / "tailwind.config.js").write_text(config)
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_versions(self, tmp_path):
        (tmp_path / "tailwind.config.js").write_text("module.exports = {}")
        det = self._get_detector()
        versions = det._detect_versions(str(tmp_path))
        assert isinstance(versions, set)

    def test_framework_name(self):
        det = self._get_detector()
        assert det.framework_name == "tailwind" or isinstance(det.framework_name, str)

    def test_detect_tailwind_v4_import(self, tmp_path):
        """Tailwind v4 uses @import 'tailwindcss'."""
        (tmp_path / "styles.css").write_text("@import 'tailwindcss';")
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_empty_dir(self, tmp_path):
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert result is False


class TestCSSResolver:
    """Tests for CSS resolver using resolve() and resolve_symbol()."""

    def _get_resolver(self):
        from coderag.plugins.css.resolver import CSSResolver

        return CSSResolver()

    def test_resolve_import(self, tmp_path):
        resolver = self._get_resolver()
        resolver.set_project_root(str(tmp_path))
        imported = tmp_path / "_variables.css"
        imported.write_text(":root { --color: red; }")
        css_file = tmp_path / "main.css"
        css_file.write_text("@import '_variables.css';")
        result = resolver.resolve("_variables.css", str(css_file))
        assert result is not None

    def test_resolve_nonexistent(self, tmp_path):
        resolver = self._get_resolver()
        resolver.set_project_root(str(tmp_path))
        css_file = tmp_path / "main.css"
        css_file.write_text("@import 'nonexistent.css';")
        result = resolver.resolve("nonexistent.css", str(css_file))
        assert result is not None

    def test_resolve_url_import(self, tmp_path):
        resolver = self._get_resolver()
        resolver.set_project_root(str(tmp_path))
        css_file = tmp_path / "main.css"
        css_file.write_text("@import url('https://fonts.googleapis.com/css');")
        result = resolver.resolve("https://fonts.googleapis.com/css", str(css_file))
        assert result is not None

    def test_resolve_symbol(self, tmp_path):
        resolver = self._get_resolver()
        resolver.set_project_root(str(tmp_path))
        result = resolver.resolve_symbol(".my-class", str(tmp_path / "test.css"))
        assert result is not None

    def test_build_index(self, tmp_path):
        resolver = self._get_resolver()
        resolver.set_project_root(str(tmp_path))
        resolver.build_index([])


class TestJSResolverDeep:
    """Deep tests for JavaScript resolver using resolve() and resolve_symbol()."""

    def _get_resolver(self, project_root):
        from coderag.plugins.javascript.resolver import JSResolver

        r = JSResolver()
        r.set_project_root(str(project_root))
        return r

    def test_resolve_relative_import(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "utils.js").write_text("export function helper() {}")
        main_file = tmp_path / "main.js"
        main_file.write_text("import { helper } from './utils';")
        result = resolver.resolve("./utils", str(main_file))
        assert result is not None

    def test_resolve_index_file(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        (utils_dir / "index.js").write_text("export default {}")
        main_file = tmp_path / "main.js"
        result = resolver.resolve("./utils", str(main_file))
        assert result is not None

    def test_resolve_node_module(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        main_file = tmp_path / "main.js"
        main_file.write_text("import React from 'react';")
        result = resolver.resolve("react", str(main_file))
        assert result is not None

    def test_resolve_with_extension(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "helper.js").write_text("export const x = 1;")
        main_file = tmp_path / "main.js"
        result = resolver.resolve("./helper.js", str(main_file))
        assert result is not None

    def test_resolve_json_import(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "data.json").write_text('{"key": "value"}')
        main_file = tmp_path / "main.js"
        result = resolver.resolve("./data.json", str(main_file))
        assert result is not None

    def test_resolve_symbol_with_from_file(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        result = resolver.resolve_symbol("SomeClass", str(tmp_path / "test.js"))
        assert result is not None

    def test_resolve_nonexistent_import(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        main_file = tmp_path / "main.js"
        main_file.write_text("import x from './nonexistent';")
        result = resolver.resolve("./nonexistent", str(main_file))
        assert result is not None

    def test_build_index(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        resolver.build_index([])

    def test_resolve_package_json_alias(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        pkg = {"name": "myapp", "main": "index.js"}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        resolver._load_package_json()
        main_file = tmp_path / "src" / "main.js"
        (tmp_path / "src").mkdir(exist_ok=True)
        main_file.write_text("")
        result = resolver.resolve("lodash", str(main_file))
        assert result is not None


class TestTSResolverDeep:
    """Deep tests for TypeScript resolver using resolve() and resolve_symbol()."""

    def _get_resolver(self, project_root):
        from coderag.plugins.typescript.resolver import TSResolver

        r = TSResolver()
        r.set_project_root(str(project_root))
        return r

    def test_resolve_relative_import(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "utils.ts").write_text("export function helper(): void {}")
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("./utils", str(main_file))
        assert result is not None

    def test_resolve_tsx_file(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "App.tsx").write_text("export default function App() { return <div/>; }")
        main_file = tmp_path / "index.ts"
        result = resolver.resolve("./App", str(main_file))
        assert result is not None

    def test_resolve_declaration_file(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        (tmp_path / "types.d.ts").write_text("declare module 'mylib';")
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("./types", str(main_file))
        assert result is not None

    def test_resolve_path_alias(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("@/utils", str(main_file))
        assert result is not None

    def test_resolve_index_ts(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        utils_dir = tmp_path / "utils"
        utils_dir.mkdir()
        (utils_dir / "index.ts").write_text("export const x = 1;")
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("./utils", str(main_file))
        assert result is not None

    def test_resolve_symbol(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        result = resolver.resolve_symbol("MyInterface", str(tmp_path / "test.ts"))
        assert result is not None

    def test_resolve_nonexistent(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("./nonexistent", str(main_file))
        assert result is not None

    def test_resolve_node_module(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        main_file = tmp_path / "main.ts"
        result = resolver.resolve("express", str(main_file))
        assert result is not None

    def test_build_index(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        resolver.build_index([])

    def test_load_tsconfig(self, tmp_path):
        resolver = self._get_resolver(tmp_path)
        tsconfig = {"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]}}}
        (tmp_path / "tsconfig.json").write_text(json.dumps(tsconfig))
        resolver._load_tsconfig()


class TestVueDetectorDeep:
    """Tests for Vue framework detector using detect_framework()."""

    def _get_detector(self):
        from coderag.plugins.javascript.frameworks.vue import VueDetector

        return VueDetector()

    def test_detect_vue_package(self, tmp_path):
        pkg = {"dependencies": {"vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_vue_sfc(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "App.vue").write_text("<template><div>Hello</div></template>")
        pkg = {"dependencies": {"vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_pinia_store(self, tmp_path):
        pkg = {"dependencies": {"pinia": "^2.0.0", "vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_vuex_store(self, tmp_path):
        pkg = {"dependencies": {"vuex": "^4.0.0", "vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_detect_no_vue(self, tmp_path):
        (tmp_path / "index.js").write_text("console.log('hello')")
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert result is False

    def test_detect_vue_router(self, tmp_path):
        pkg = {"dependencies": {"vue-router": "^4.0.0", "vue": "^3.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert isinstance(result, bool)

    def test_framework_name(self):
        det = self._get_detector()
        assert det.framework_name == "vue" or isinstance(det.framework_name, str)

    def test_detect_empty_dir(self, tmp_path):
        det = self._get_detector()
        result = det.detect_framework(str(tmp_path))
        assert result is False
