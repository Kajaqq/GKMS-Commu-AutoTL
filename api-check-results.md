### High
1. Local quota accounting does not include SDK retry attempts.
   - Location: `ai/translator.py:55-58`, `config/config.py:47-56`.
   - The code acquires one request/day token before a logical call, but `HttpRetryOptions` can produce multiple HTTP
     attempts.
   - This is acceptable as a local burst guard, but it is not an exact quota mirror.
   - Suggested shape:
     - Document this limitation, reduce configured local request caps to leave retry headroom, or move retries outside
       the SDK if exact local accounting is required.

### Medium

2. Per-file failures are swallowed after printing.
   - Location: `process_excel_files.py:266-274`.
   - Exceptions are printed, then the batch returns only a processed count.
   - This can make automated usage hard because there is no structured failure list or non-zero exit behavior.
   - Suggested shape:
     - Accumulate failed file names and return/report them, or add strict mode that raises after all workers complete.

3. Formatting can silently truncate translated content.
    - Location: `utils/formatting.py:105-107`.
    - When a line-break cap applies, extra wrapped lines are dropped without a warning or `TRANSLATION_ERROR`.
    - Suggested shape:
      - Warn, mark the cell, or preserve the full text somewhere when truncation occurs.