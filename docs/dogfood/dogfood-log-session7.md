# Dogfood Session 7: Mealie (FastAPI + Vue/TypeScript)

**Date:** 2026-03-23
**Target:** [mealie-recipes/mealie](https://github.com/mealie-recipes/mealie)
**Type:** FastAPI + Vue/Nuxt + TypeScript
**Commit (fixes):** 50aa57a

---

## Project Profile

| Metric | Value |
|--------|-------|
| Total files | 1,008 |
| Python files | 573 |
| TypeScript files | 233 |
| Vue SFC files | 192 |
| JavaScript files | 5 |
| CSS/SCSS files | 4 |
| Repository size | 78 MB |

## Parse Results

### Before Bug Fixes (commit d90527a)

| Metric | Value |
|--------|-------|
| Files Parsed | 816 |
| Total Nodes | 20,552 |
| Total Edges | 42,907 |
| Parse Time | 34.4s |
| Communities | 197 |
| Avg Confidence | 0.78 |
| .vue files parsed | 0 ❌ |
| Phantom PHP nodes | 3,687 ❌ |

### After Bug Fixes (commit 50aa57a)

| Metric | Value |
|--------|-------|
| Files Parsed | 1,008 |
| Total Nodes | 18,895 |
| Total Edges | 53,380 |
| Parse Time | 42.2s |
| .vue files parsed | 191 ✅ |
| Phantom PHP nodes | 0 ✅ |
| Vue components detected | 192 ✅ |
| Vue hooks detected | 43 ✅ |

## Frameworks Detected

| Framework | Details |
|-----------|--------|
| FastAPI ✅ | 254 routes, 43 models, 4 middleware |
| Vue ✅ | 192 components, 43 hooks, 1 route |

## Bugs Found & Fixed

### BUG #1 (HIGH): .vue files NOT parsed

**Severity:** HIGH
**Impact:** 192 Vue SFC files completely invisible to CodeRAG

**Root cause:** Neither the TypeScript plugin (`.ts/.cts/.tsx/.mts`) nor the JavaScript plugin (`.jsx/.cjs/.js/.mjs`) included `.vue` in their `file_extensions`.

**Fix:**
- Added `.vue` to TypeScript plugin's `file_extensions`
- Added `_extract_vue_script()` method to TypeScript extractor that:
  - Finds `<script>` blocks (prioritizes `setup` > `lang="ts"` > plain)
  - Extracts content between `<script>` and `</script>` tags
  - Calculates line offset for correct node positions
  - Parses extracted script with tree-sitter TSX parser
  - Skips `<script type="application/json">` blocks
- Added `.vue` → `"typescript"` mapping in `detect_language()`

**Files modified:** `plugins/typescript/plugin.py`, `plugins/typescript/extractor.py`, `core/models.py`

### BUG #2 (HIGH): Phantom PHP language on placeholder nodes

**Severity:** HIGH
**Impact:** 3,687 phantom PHP nodes in a project with ZERO PHP files, corrupting cross-language edge statistics

**Root cause:** `resolver.py` line 219 had `language="php"` hardcoded when creating placeholder nodes for unresolved external references:
```python
placeholder = Node(
    ...
    language="php",  # BUG: hardcoded!
)
```

**Fix:**
- `resolve()` now passes `result.language` from each `ExtractionResult` to `_resolve_one()`
- `_resolve_one()` accepts `source_language` parameter (default `"unknown"`) and uses it for placeholder nodes
- External placeholders now correctly labeled by source language

**Files modified:** `pipeline/resolver.py`

## Feature Tests

| Feature | Status | Notes |
|---------|--------|-------|
| Parse | ✅ PASS | 1,008 files in 42.2s |
| Framework detection | ✅ PASS | FastAPI + Vue correctly detected |
| Launcher (dry-run) | ✅ PASS | CLAUDE.md generated (47 lines) |
| CLAUDE.md | ⚠️ PARTIAL | PageRank shows external/test symbols at top |
| Query: MealieModel | ✅ PASS | Found as imports |
| Query: Recipe model | ✅ PASS | Found RecipeNote, RecipeDuplicate, RecipeLastMade |
| Query: GET /recipes | ❌ FAIL | FTS5 doesn't match HTTP method + path well |
| Query: recipes (routes) | ✅ PASS | Found 10 recipe routes |
| Query: useUserApi | ✅ PASS | Found as vue:composable:useUserApi |
| Query: CRUDRouter | ✅ PASS | Found fastapi.include_router modules |
| Query: BaseButton | ✅ PASS | Found as component (after .vue fix) |
| Query: useRecipe | ✅ PASS | Found 3 composables |
| Session memory | ✅ PASS | Empty (expected for fresh project) |
| Cost benchmark | ✅ PASS | 99.8% savings ($3,449 → $5.76/month) |
| Dependency graph | ✅ PASS | MealieModel shows 13 dependencies |
| Cross-language edges | ⚠️ PARTIAL | ts↔js edges work, python↔ts minimal (1 edge) |

**Query accuracy:** 9/11 (81.8%)

## Observations

### ISSUE #1 (MEDIUM): CLAUDE.md PageRank shows external symbols
The architecture overview in CLAUDE.md shows `pydantic.UUID4`, `pathlib.Path`, `TestUser`, `TestClient` at the top instead of internal application symbols like `MealieModel`, `Recipe`, etc. External dependencies and test utilities should be deprioritized.

### ISSUE #2 (LOW): Cross-language Python↔TypeScript matching weak
Only 1 `typescript→python` edge detected. The cross-language matcher doesn't effectively connect FastAPI routes to TypeScript frontend fetch calls. This is because Mealie uses a generated API client (`~/lib/api/`) rather than direct fetch calls with URL strings.

### ISSUE #3 (LOW): Route search with HTTP method prefix fails
Searching for `GET /recipes` returns no results, while searching for just `recipes` with `--kind route` works. FTS5 tokenization doesn't handle the HTTP method + path pattern well.

## Cumulative Dogfood Stats

| Metric | Session 7 | Cumulative (7 sessions) |
|--------|-----------|------------------------|
| Files | 1,008 | 18,574 |
| Nodes | 18,895 | 255,025 |
| Edges | 53,380 | 730,590 |
| Bugs found | 2 | 17 |
| Bugs fixed | 2 | 17 |
| Tests | 26 new | 4,420+ |
