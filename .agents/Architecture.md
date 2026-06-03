# Architecture

## What

GKMS-Commu-AutoTL is a local batch translator for Gakumas communication Excel files. It reads `.xlsx` files from
`IN/`, translates untranslated Japanese source rows to English with the Gemini API, formats the translated text for
game UI constraints, and writes translated workbooks to `OUT/`.

The tool is intentionally small: `process_excel_files.py` owns workbook orchestration, `ai/` owns Gemini and validation
models, `config/` owns prompts and constants, and `utils/` owns parsing, cleanup, and wrapping helpers.

## Why

The project keeps the Excel workbook contract explicit and stable while letting translation quality improve through
prompt context, structured Gemini output, and deterministic post-processing. The model receives only relevant glossary
and character-style references for the current batch, then response parsing catches malformed, duplicate, unexpected,
missing, and empty translations before results are written back to the workbook.

## Where

- `process_excel_files.py`: runtime entry point and workbook workflow.
- `ai/translator.py`: Gemini client selection, request execution, token counting, and local rate-limit acquisition.
- `ai/utils.py`: thread-safe request/token/day limiters and translation-specific exceptions.
- `ai/Models.py`: dataclass prompt objects plus Pydantic response schemas and line-number validation.
- `config/config.py`: env-driven Gemini model/tier/retry config, folder paths, Excel headers, quota caps, and formatting rules.
- `config/prompts.py`: system instruction, batch prompt template, and per-line prompt format.
- `config/dictionary.py`: canonical Japanese term/name translations.
- `config/character_styles.py`: character voice guidance keyed by English display names with Japanese aliases.
- `utils/translator_helper.py`: prompt reference filtering and Pydantic-backed Gemini response parsing.
- `utils/text_utils.py`: cell normalization, safe string conversion, whitespace stripping, quote removal, and punctuation cleanup.
- `utils/formatting.py`: message/file-type-aware line wrapping for translated cell values.
- `README.md`: user-facing setup and usage notes.
- `AGENTS.md`: agent-facing repository rules and implementation guidance.

## Dataflow

```text
IN/*.xlsx
  |
  v
process_excel_files_in_folder()
  - creates OUT/
  - finds .xlsx files
  - creates one shared GeminiTranslationClient
  - processes files with ThreadPoolExecutor
  |
  v
WorkbookTranslator.process()
  |
  +--> load_workbook()
  |     - opens workbook with openpyxl
  |     - uses active sheet
  |
  +--> validate_header_row()
  |     - requires row 1 to equal:
  |       type, name, translated name, text, translated text
  |
  +--> collect_rows()
  |     - skips header
  |     - skips merged target cells
  |     - translates rows with source text and an empty or TRANSLATION_ERROR target
  |     - optionally resolves exact single-term matches from config/dictionary.py
  |     - creates SourceLine(line_number, speaker, text)
  |
  +--> translate_rows()
  |     |
  |     +--> get_prompt_references()
  |     |     - includes glossary entries only when the Japanese term appears in source text
  |     |     - includes character styles only when a speaker alias/name matches the batch
  |     |
  |     +--> TranslationPrompt.__str__()
  |     |     - renders config/prompts.py templates with source lines and references
  |     |
  |     +--> GeminiTranslationClient.translate_batch()
  |           - lazily creates genai.Client(http_options=retry_options)
  |           - lets google-genai resolve auth/backend settings from the environment
  |           - counts local prompt tokens
  |           - acquires local RPM, TPM, and RPD limits
  |           - calls client.models.generate_content()
  |           - requests application/json matching TranslationResponse
  |
  +--> parse_translation_response()
  |     - validates JSON with TranslationResponse.model_validate_json()
  |     - rejects duplicate or unexpected line numbers
  |     - turns empty returned text into TRANSLATION_ERROR
  |     - fills missing expected line numbers with TRANSLATION_ERROR
  |
  +--> write_translations()
  |     - chooses dictionary translation or parsed API translation by workbook line number
  |     - applies wrap_text()
  |     - writes to translated text cells
  |
  +--> save()
        - creates OUT/ if needed
        - saves translated workbook under the source file name

process_excel_files_in_folder()
  - records failed files and files saved with TRANSLATION_ERROR rows
  - prints a batch summary
  - returns a processed-file count and an error flag used for the CLI exit code
```

## Workbook Contract

The active sheet must use this exact first-row header order after lowercase normalization:

```text
type | name | translated name | text | translated text
```

Rows are enumerated starting at `1` for the first data row, not the physical Excel row number. That line number is the
ID sent to Gemini and later used to map validated translations back to target cells.

A row needs translation when:

- `text` is non-empty, and
- `translated text` is empty or starts with `TRANSLATION_ERROR`.

Merged cells in the target column are skipped because the tool cannot reliably write or wrap them.

## Gemini Integration

The code uses the current `google-genai` SDK. `config/config.py` loads `.env` and defines the configured model, local
usage tier, system instruction, JSON MIME type, Pydantic response schema, thinking config, service tier, timeout, and
retry policy. `ai/translator.py` handles lazy client creation and request execution with
`genai.Client(http_options=ModelConfig.retry_options)`.

Authentication/backend selection is delegated to the SDK environment handling. `.env.sample` documents the repo-level
settings:

- `GEMINI_API_KEY` for Google AI Studio API-key authentication.
- `GOOGLE_GENAI_USE_ENTERPRISE=True` for the enterprise/ADC path and enterprise local quota tier.
- `PAID_TIER=True` to use paid-tier local quota caps when not in enterprise mode.
- `GOOGLE_GENAI_USE_FLEX_MODE=True` to request the flex service tier and use the longer flex timeout.

Local quota controls are process-local and shared by the single `GeminiTranslationClient` passed to worker threads.
They prevent bursts across parallel workbook processing but are not a distributed quota system. Daily request limits
reset at Pacific midnight.

## Validation And Error Handling

Gemini output is expected to be JSON matching `TranslationResponse`:

```json
{
  "translations": [
    {
      "line_number": 1,
      "text": "Translated text"
    }
  ]
}
```

Pydantic validation forbids extra fields and strict type coercion. Response validation also checks duplicate and
unexpected line numbers. Missing and empty translations are preserved as `TRANSLATION_ERROR:` cell values so reruns can
target failed rows.

## Formatting

Before writing a translation, `wrap_text()` applies deterministic cleanup and wrapping:

- strips model-added wrapping quotes or fences,
- normalizes punctuation according to `ReplacementConfig`,
- removes trailing periods from choices,
- applies special wrapping for `choice`, dialogue, `adv_pevent_002_`, and `adv_unit_` files,
- truncates wrapped lines when a configured line-break cap applies.

## Extension Points

- Add glossary or canonical name changes in `config/dictionary.py`.
- Add or revise character voice guidance in `config/character_styles.py`.
- Tune prompt behavior in `config/prompts.py`.
- Tune model, retry, quota, folders, headers, and wrapping in `config/config.py`.
- Keep workbook orchestration in `process_excel_files.py`; move reusable parsing, formatting, or Gemini-specific logic
  into the existing `utils/` or `ai/` modules when it clearly belongs there.

## Known Risks

- There is no dedicated test suite yet; minimum validation is `py_compile`, `ruff`, and `ty`.
- Full end-to-end runs call Gemini and require credentials, network access, and quota budget.
- Parallel workers share a client and local limiters, but workbook processing still writes one output file per source
  file and should not target the same output path from multiple jobs.
- Boolean-like environment values are read as strings, so unset variables are the safe default. Values such as
  `False` are still truthy in current config code.
