---
applyTo: "src/docsync/**"
---

# Coding Instructions — DocSync

## Language & Style
- Python 3.10+, type-annotated throughout
- Use `from __future__ import annotations` in every module
- Prefer dataclasses over plain dicts for structured return values
- No print() in library code — use structlog

## Security Rules
- NEVER hardcode credentials, tokens, or passwords
- All secrets must come from `os.environ`
- Sanitise HTTP exception context before re-raising (strip Authorization header from logged objects)
- Validate all external inputs with pydantic at system boundaries

## Error Handling
- Raise RuntimeError (not raw Exception) from HTTP clients so tenacity can match it
- FileNotFoundError for 404 from GitHub — callers should skip gracefully
- Fail fast on config errors (missing env vars, bad YAML) — never swallow at startup

## API Conventions
- All GitHub API calls are async (`async def`)
- All Confluence mutating calls have tenacity retry (3 attempts, exponential back-off)
- `find_page` uses `docsync:source_path` property, NOT page title
- `archive_page` is idempotent — 404 from DELETE should be swallowed

## Testing
- All external HTTP calls must be mockable (no live credentials in tests)
- Use `respx` or `pytest-httpx` for mocking httpx calls
- Use `pytest.mark.asyncio` for async tests
- Every public method needs at least one happy-path and one error-path test
