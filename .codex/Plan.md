# translator.py Minimal Rewrite Plan

## Scope

Change `translator.py` only.

Do not touch workbook flow, prompts, config defaults, models, formatting, tests, docs, or dependency files unless the user explicitly asks.

## Moyu Guidance

- Prefer deleting code over adding code.
- The final implementation should be shorter or roughly the same size.
- Do not add new abstractions, strategy classes, wrappers, config files, or dependencies.
- Do not add defensive handling for cases that cannot happen in this project.
- Keep only SDK-wrapped API/network errors. Trust `google-genai` instead of building a custom network exception list.
- Do not add candidate-count checks. This app expects one request to produce one candidate.
- Do not add tool-calling, image-generation, or `MAX_TOKENS` handling. Those are outside this xlsx translation workflow.
- Do not add safety-finish handling. Safety filters are disabled for this workflow.
- If a helper does not reduce total code or clarify an actual repeated operation, inline it.

## Implementation Steps

1. Remove post-response token reconciliation.
   - Delete `TokenBucketRateLimiter.update_actual()`.
   - Delete `_response_input_token_count()`.
   - Delete the `actual_input_tokens` / `update_actual()` block in `translate_batch()`.
   - Use the estimated token count only.

2. Fix token estimation.
   - Change `_estimate_tokens()` to use ceiling division:

   ```python
   return max(1, (len(prompt_text) + chars_per_token - 1) // chars_per_token)
   ```

   - Do not add multipliers, reserves, or new config values.

3. Stop silently clamping oversized token requests.
   - In `TokenBucketRateLimiter.acquire()`, keep the lower bound of `1`.
   - If requested tokens exceed bucket capacity, raise a clear `GeminiTranslationError`.
   - Do not clamp oversized requests down to capacity.

4. Create the Gemini client before consuming local quota.
   - In `translate_batch()`, call `_get_client()` before `_acquire_rate_limits()`.
   - Use the returned local `client` for `generate_content()`.
   - Missing credentials, invalid local config, or client construction failure must not consume local quota.

5. Make limiter acquisition less self-corrupting.
   - In `_acquire_rate_limits()`, acquire local daily quota before RPM and TPM:

   ```python
   daily -> request -> token
   ```

   - Do not add rollback/refund logic.

6. Replace string-based quota guessing with SDK-first retry handling.
   - Catch `genai_errors.APIError` explicitly before generic exceptions.
   - Use `error.code` and, if useful, `error.status`.
   - Retry only clear API transient statuses:
     - `429`
     - `500`
     - `502`
     - `503`
     - `504`
   - Keep `genai_errors.ServerError` retryable if that makes the code shorter or clearer.
   - Remove `_is_daily_quota_error()` entirely.
   - Remove generic `"quota"` / `"resource_exhausted"` / English-prose substring classification.
   - Local `GeminiDailyQuotaExhaustedError` stays non-retryable.
   - Unknown generic exceptions should be wrapped as `GeminiTranslationError` without retrying.

7. Keep empty response handling simple.
   - Keep `EmptyGeminiResponseError` retryable if the existing behavior is still desired.
   - Do not add finish-reason taxonomy.
   - Do not add candidate inspection.

8. Reduce helpers.
   - Remove helpers that are no longer used.
   - Simplify `_is_rate_limit_error()` and `_is_retryable_error()`, or inline them if that produces less code.
   - Do not split the retry logic into more helper functions unless total code decreases.

## Acceptance Criteria

- `translator.py` has fewer or roughly the same number of lines.
- `update_actual()` is gone.
- `_response_input_token_count()` is gone.
- `_is_daily_quota_error()` is gone.
- Oversized TPM acquisitions fail clearly instead of being clamped.
- Client setup happens before local quota acquisition.
- Local daily quota acquisition happens before RPM/TPM acquisition.
- Retry behavior is based on `google-genai` API errors, not English string matching.
- No new files besides this plan.
- No new dependencies.

## Verification

Run:

```bash
uv run python -m py_compile translator.py
uv run ruff check translator.py
uv run ty check translator.py
```
