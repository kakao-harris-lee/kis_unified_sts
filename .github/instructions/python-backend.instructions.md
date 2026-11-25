---
globs: ["**/*.py", "*.py"]
---

# Python Backend Rules

> **Loading**: the `globs` frontmatter above **is enforced**. The OMC `rules-injector` hook supports `globs` (`src/hooks/rules-injector/types.ts:18`) and injects this file as `[Rule: …][Match: …]` when a matching path is read/written/edited (`constants.ts:45` `TRACKED_TOOLS`). Scope is structural, not advisory.
>
> This file previously lived at `.claude/rules/`, where scope was defeated — not by `globs`, but by the **location**: Claude Code loads `.claude/rules/*.md` in full into the system prompt at session start regardless of which files are open (observed directly; `.github/` has no such unconditional load). It was moved here so the declared scope is the actual scope. `.github/instructions/` requires the `.instructions.md` suffix (`finder.ts:36-41`).
>
> **`*.py` is not a redundant duplicate of `**/*.py` — do not delete it.** `matchGlob` (`matcher.ts:17-28`) turns `**/*.py` into `^.*/[^/]*\.py$`, whose literal `/` excludes files sitting **directly at the repo root** (`setup.py`, `conftest.py`). The bare `*.py` form covers them. Paths are matched relative to the project root (`matcher.ts:52-57`).
>
> **This file stays at the repo root because `shared/`, `services/`, `tests/` carry no project marker of their own** — `findProjectRoot` (`finder.ts:57-63`) therefore walks them up to the repo root's `.git`/`pyproject.toml` (`constants.ts:17-24`). Any directory that grows its own `pyproject.toml` / `.venv` becomes a separate project root and stops seeing this file; it would need its own `.github/instructions/` (this is exactly why the frontend rules live under `strategy-builder-ui/`).
>
> Each rule has a "why" so you can override it intentionally rather than blindly.

## Code Style
- Type hints on ALL function signatures (parameters and return types) — *enables `mypy --strict` and IDE autocomplete; required by FastAPI/Pydantic v2 for response_model inference*
- Docstrings on all public functions and classes (Google style) — *parsed by Sphinx/mkdocstrings; downstream callers see hover hints*
- Use `pathlib.Path` instead of `os.path` — *cross-platform paths, chainable API, `.exists()`/`.read_text()` without import gymnastics*
- Prefer f-strings over `.format()` or `%` — *fastest path on CPython 3.12+; lower cognitive load*
- Use `logging` module, never `print()` for non-debug output — *level filtering, structured handlers, captured by pytest's `caplog` fixture*
- Constants in UPPER_SNAKE_CASE at module level — *grep-friendly, distinguishable from runtime values*

## Error Handling
- Handle exceptions explicitly — never use bare `except:` — *bare except swallows `KeyboardInterrupt` and `SystemExit`, hides real bugs*
- Use custom exception classes for domain errors — *callers can `except DomainError` without coupling to library-specific exception types*
- Always log exceptions with traceback: `logger.exception("message")` — *not `logger.error(str(e))` which loses the stack*
- Return meaningful error messages to API callers — *FastAPI: prefer `HTTPException(status_code, detail)` over generic 500*

## Architecture
- Use Pydantic v2 models for request/response validation — *catches malformed input at the boundary; auto-generates OpenAPI*
- Async endpoints where I/O is involved (`await db.execute(...)`, `await http.get(...)`) — *sync handlers block the event loop and serialise the entire app*
- Dependency injection (FastAPI `Depends`) for testability — *swap real DB session for in-memory in tests without monkey-patching*
- Repository pattern for database access — *isolates SQL/ORM details from business logic; one place to add caching*
- Service layer between routes and repositories — *route handlers stay thin (parse → call service → serialise); business logic is unit-testable without HTTP*

## Testing
- Use pytest with fixtures (not `unittest.TestCase`) — *first-class parametrize, smaller boilerplate, plugin ecosystem (`pytest-asyncio`, `pytest-mock`, `pytest-cov`)*
- Mock external services (API calls, database) in unit tests — *unit tests must run in <1 s each; integration tests live in a separate folder*
- Use factories for test data (`factory_boy`, `polyfactory`), not hardcoded dictionaries — *changes to a model don't break 50 unrelated tests*
- Async tests with `pytest-asyncio` and `@pytest.mark.asyncio` — *required for `async def` tests; otherwise pytest treats them as coroutines and skips silently*
- Each test function tests ONE thing — *failure message names exactly what regressed; no shotgun debugging*
