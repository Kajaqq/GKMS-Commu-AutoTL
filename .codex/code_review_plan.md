# code_review_plan.md

## Scope

Implement a small `translator.py` cleanup based on the review findings, without changing workbook flow, prompts, config defaults, dependencies, or unrelated modules.

`IN/` is not present in the current checkout, so there is no sample workbook to inspect. The plan is therefore limited to issues that can happen in the existing command-line workflow: one shared `GeminiTranslationClient`, parallel workbook workers, text-only Gemini requests, and JSON structured output parsing downstream.

## Changes

1. Treat whitespace-only Gemini responses as empty.
   - Strip response text inside `_require_response_text()`.
   - Return the stripped text from `_require_response_text()`.
   - Retry the existing `EmptyGeminiResponseError` path for whitespace-only responses.

2. Prevent oversized prompts from consuming local daily/RPM quota.
   - Add a non-consuming capacity validation to `TokenBucketRateLimiter`.
   - Call it for `_input_token_limiter` at the start of `_acquire_rate_limits()`, before daily/RPM acquisition.
   - Keep the existing acquisition order after validation: daily, RPM, TPM.
   - Keep the existing token estimate; do not add API token-count calls or reserves.

3. Keep retry handling SDK-first and narrow.
   - Preserve retrying `genai_errors.APIError` for `429`, `500`, `502`, `503`, and `504`.
   - Do not add string matching against quota messages.
   - Do not add broad network exception taxonomies.

4. Do not implement the broader review wishlist.
   - No persistent daily quota store.
   - No new config fields.
   - No new dependencies.
   - No candidate/finish-reason inspection.
   - No timeout wiring because the current timeout location is `ModelConfig.generation_config` / `HttpOptions`, which lives in `config.py`.

## Verification

Run these after implementation:

```bash
uv run python -m py_compile translator.py
uv run ruff check .
uv run ty check translator.py
uv run python -c "exec('from translator import EmptyGeminiResponseError, _require_response_text\nR = type(\"R\", (), {\"text\": \"   \"})\ntry:\n    _require_response_text(R())\nexcept EmptyGeminiResponseError:\n    pass\nelse:\n    raise SystemExit(\"whitespace response was accepted\")')"
uv run python -c "exec('from translator import GeminiTranslationError, TokenBucketRateLimiter\nlimiter = TokenBucketRateLimiter(10)\ntry:\n    limiter.validate_capacity(11)\nexcept GeminiTranslationError:\n    pass\nelse:\n    raise SystemExit(\"oversized token request was accepted\")')"
```

The final required gate is:

```bash
uv run ruff check .
```
