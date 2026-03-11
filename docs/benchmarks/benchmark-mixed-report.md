# CodeRAG Mixed-Language Benchmark Report

**Date:** 2025-03-11  
**CodeRAG Version:** P1 (PHP + JavaScript + TypeScript plugins)  
**Test:** 4 mixed PHP + JS/TS repositories  

---

## Summary

| Metric | Value |
|--------|-------|
| Repositories tested | 4 |
| Total files parsed | 8,212 |
| Total nodes extracted | 81,178 |
| Total edges created | 185,371 |
| Query accuracy | 100% (35/35) |
| Parse success rate | 100% (4/4) |
| Cross-language edges found | 15 (Flarum) |

---

## Repository Results

| Repository | Description | PHP | JS | TS | Total Files | Nodes | Edges | Time |
|-----------|-------------|-----|----|----|-------------|-------|-------|------|
| **koel** | Music streaming (Laravel + Vue/TS) | 1,036 | 6 | 525 | 1,567 | 15,034 | 32,860 | 9.1s |
| **monica** | Personal CRM (Laravel + Vue) | 1,649 | 8 | 0 | 1,657 | 20,697 | 52,841 | 15.6s |
| **flarum** | Forum framework (PHP + JS/TS) | 1,358 | 207 | 990 | 2,555 | 28,250 | 64,603 | 17.9s |
| **bagisto** | E-commerce (Laravel + Vue) | 2,253 | 36 | 143 | 2,432 | 17,197 | 35,067 | 14.7s |

---

## Edge Type Distribution

### Koel (PHP + TS)
| Edge Type | Count |
|-----------|-------|
| calls | 11,856 |
| contains | 11,162 |
| imports | 7,201 |
| extends | 666 |
| has_type | 638 |
| instantiates | 594 |
| exports | 274 |
| implements | 165 |
| uses_trait | 145 |
| imports_type | 95 |
| returns_type | 64 |

### Monica (PHP + JS)
| Edge Type | Count |
|-----------|-------|
| calls | 23,212 |
| contains | 17,320 |
| imports | 8,865 |
| instantiates | 1,295 |
| extends | 1,113 |
| uses_trait | 725 |
| implements | 304 |
| exports | 7 |

### Flarum (PHP + JS + TS)
| Edge Type | Count |
|-----------|-------|
| calls | 22,402 |
| contains | 21,482 |
| imports | 9,757 |
| returns_type | 2,584 |
| extends | 2,086 |
| has_type | 1,875 |
| instantiates | 1,527 |
| exports | 833 |
| imports_type | 654 |
| implements | 395 |
| renders | 389 |
| passes_prop | 320 |
| uses_trait | 268 |
| re_exports | 31 |

### Bagisto (PHP + Vue/TS)
| Edge Type | Count |
|-----------|-------|
| calls | 15,305 |
| contains | 12,074 |
| imports | 5,478 |
| extends | 845 |
| instantiates | 519 |
| has_type | 370 |
| uses_trait | 189 |
| implements | 163 |
| exports | 114 |
| returns_type | 10 |

---

## Cross-Language Analysis

### Symbol Counts by Language

| Repository | PHP Classes | JS Classes | TS Classes | PHP Functions | JS Functions | TS Functions |
|-----------|------------|-----------|-----------|--------------|-------------|-------------|
| koel | 868 | 0 | 20 | 28 | 11 | 126 |
| monica | 1,306 | 0 | 0 | 0 | 5 | 0 |
| flarum | 1,066 | 71 | 572 | 1 | 70 | 90 |
| bagisto | 985 | 0 | 9 | 1 | 2 | 90 |

### Cross-Language Edges (PHP ↔ JS/TS)

Only **Flarum** produced cross-language edges (15 total), which is expected since it has the most balanced PHP/JS/TS split. These edges are name-based matches from the reference resolver:

| Edge Type | Source (JS/TS) | Target (PHP) | Confidence |
|-----------|---------------|-------------|------------|
| calls | PostPreview.js → `username()` | UserResourceFields.php | 0.70 |
| calls | UserCard.js → `username()` | UserResourceFields.php | 0.70 |
| calls | slidable.js → `activate()` | User.php | 0.70 |
| calls | slidable.js → `reset()` | Migrator.php | 0.70 |
| calls | textFormatter.js → `username()` | UserResourceFields.php | 0.70 |
| calls | common.js → `makeUser()` | NotificationMailerTest.php | 0.70 |
| imports | compiler.js → `path()` | RouteCollectionUrlGenerator.php | 0.70 |
| instantiates | SuspensionInfoModal.js → `Date` | Date.php | 0.85 |
| instantiates | SuspendUserModal.js → `Date` | Date.php | 0.85 |

> **Note:** These are coincidental name matches (shared method names like `username`, `Date`), not semantic API connections. True cross-language API matching (PHP routes ↔ JS fetch calls) is planned for P2.

---

## Query Accuracy

### Standard Queries (20/20 = 100%)

| Repository | Query | Type | Result |
|-----------|-------|------|--------|
| koel | Song | PHP class | ✅ |
| koel | SongListControls | TS component | ✅ |
| koel | PlaybackService | PHP/TS service | ✅ |
| koel | UserController | PHP controller | ✅ |
| koel | useSongList | TS composable | ✅ |
| monica | Contact | PHP model | ✅ |
| monica | ContactController | PHP controller | ✅ |
| monica | Account | PHP model | ✅ |
| monica | User | PHP model | ✅ |
| monica | ActivityController | PHP controller | ✅ |
| flarum | Discussion | PHP/JS model | ✅ |
| flarum | PostStream | JS component | ✅ |
| flarum | Forum | PHP/JS | ✅ |
| flarum | UserController | PHP controller | ✅ |
| flarum | CommentPost | PHP/JS | ✅ |
| bagisto | Product | PHP model | ✅ |
| bagisto | CartController | PHP controller | ✅ |
| bagisto | Customer | PHP model | ✅ |
| bagisto | OrderController | PHP controller | ✅ |
| bagisto | Category | PHP model | ✅ |

### Cross-Language Queries (15/15 = 100%)

| Repository | Query | Expected Language | Result |
|-----------|-------|------------------|--------|
| koel | SongController | PHP | ✅ |
| koel | songStore | TS | ✅ |
| koel | PlaylistService | PHP | ✅ |
| koel | usePlaylistManagement | TS | ✅ |
| koel | Authenticatable | PHP | ✅ |
| flarum | DiscussionController | PHP | ✅ |
| flarum | DiscussionList | JS | ✅ |
| flarum | PostRepository | PHP | ✅ |
| flarum | PostStream | JS | ✅ |
| flarum | ExtensionManager | PHP/JS | ✅ |
| bagisto | ProductController | PHP | ✅ |
| bagisto | CartRepository | PHP | ✅ |
| bagisto | Customer | PHP | ✅ |
| bagisto | checkout | JS/TS | ✅ |
| bagisto | OrderRepository | PHP | ✅ |

---

## Cumulative Benchmark Totals (All 29 Repositories)

| Category | Repos | Files | Nodes | Edges |
|----------|-------|-------|-------|-------|
| PHP (10 repos) | 10 | 33,896 | 516,705 | 1,359,239 |
| JS/TS (15 repos) | 15 | 49,637 | 351,964 | 761,981 |
| Mixed (4 repos) | 4 | 8,212 | 81,178 | 185,371 |
| **TOTAL** | **29** | **91,745** | **949,847** | **2,306,591** |

---

## Key Observations

1. **Multi-language parsing works seamlessly** — all three plugins (PHP, JS, TS) activate automatically based on file extensions within the same repository
2. **Flarum is the best test case** for cross-language work — it has the most balanced PHP/JS/TS split (1,358/207/990) and produced 15 cross-language edges
3. **Edge type richness scales with language diversity** — Flarum produced 14 distinct edge types vs 8 for Monica (PHP-only)
4. **TypeScript-specific edges** (`has_type`, `returns_type`, `imports_type`) appear in repos with TS code (koel, flarum, bagisto)
5. **Performance is consistent** — 9-18 seconds for repos with 1,500-2,500 files regardless of language mix
6. **Cross-language name-based matching** produces some false positives (e.g., JS `Date` → PHP `Date.php`) — P2's API-aware matching will improve precision
