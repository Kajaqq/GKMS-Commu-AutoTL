# Architecture

## Purpose

GKMS-Commu-AutoTL is a batch translator for Gakuen Idolmaster commu Excel files. It reads `.xlsx` workbooks from `IN/`, translates missing Japanese text into English with Gemini, applies game-specific cleanup and line wrapping, and writes translated workbooks to `OUT/`.

The application is intentionally a small script pipeline rather than a service. Most state lives in the workbook being processed, while configuration and translation rules live in Python modules.

## Runtime Entry Points

| What | Where | Why |
| --- | --- | --- |
| Main Python entry point | `process_excel_files.py` | Orchestrates folder scanning, workbook loading, row selection, API calls, formatting, and saving. |
| Windows convenience runner | `run.bat` | Runs `uv run process_excel_files.py` for users launching from Windows. |
| Package/dependency definition | `pyproject.toml` | Declares Python version and runtime dependencies: `google-genai`, `openpyxl`, `python-dotenv`, and related packages. |

## Module Responsibilities

| Module | What it owns | Why it exists |
| --- | --- | --- |
| `process_excel_files.py` | End-to-end workbook workflow, header detection, row filtering, prompt construction, response parsing, and writing translated cells. | Keeps the script runnable from one place and coordinates all supporting modules. |
| `translator.py` | Gemini client creation and `generate_content` API calls. | Isolates external API setup and error conversion from workbook logic. |
| `config.py` | Model, language, folder, Excel header, and formatting constants. | Centralizes values that tune behavior without changing the pipeline code. |
| `prompts.py` | System instruction, batch prompt template, and per-line prompt format. | Keeps model instructions separate from the mechanics of reading Excel rows. |
| `character_styles.py` | Character voice/style descriptions. | Supplies persona guidance to the translation prompt so output can vary by speaker. |
| `dictionary.py` | Fixed Japanese-to-English term/name translations. | Avoids API calls for exact known names and terms, and keeps canonical spellings stable. |
| `formatting.py` | Text cleanup integration, line wrapping, choice/dialogue/file-prefix layout rules. | Converts raw translations into strings that fit expected game UI constraints. |
| `text_utils.py` | Cell string normalization, model-output cleanup, punctuation normalization. | Shares low-level text handling between header detection and output formatting. |

## Dataflow

```text
IN/*.xlsx
  -> process_excel_files_in_folder()
  -> process_workbook()
  -> locate_header_row()
  -> collect rows needing translation
       -> exact dictionary match?
            yes -> NAME_TERM_TRANSLATIONS
            no  -> LINE_FORMAT_TEMPLATE batch lines
  -> request_translations_from_api()
       -> TRANSLATION_PROMPT_TEMPLATE + CHARACTER_SPEAKING_STYLES
       -> translate_batch_with_gemini()
       -> Gemini API response text
       -> regex parse "Line N: translation"
  -> choose translated text per pending row
  -> wrap_text()
       -> clean_text()
       -> resolve_wrap_params()
       -> textwrap/per-line wrapping
  -> write target cells
  -> OUT/<same filename>.xlsx
```

## Workbook Processing Flow

1. `process_excel_files_in_folder()` resolves the source and output folders from `TranslatorConfig`.
2. It creates `OUT/` if needed, scans `IN/` for `*.xlsx`, and processes files in sorted order.
3. `process_workbook()` loads each workbook with `openpyxl` and uses only the active sheet.
4. `locate_header_row()` scans the first ten rows for the configured source header, currently `text`.
5. The header row is normalized with `normalize_cell()`, producing a map from lower-case header text to 1-based Excel column indexes.
6. The pipeline requires `text` and `translated text` columns. It optionally uses `translated name` as speaker context and `type` for formatting rules.
7. Each data row is considered for translation when:
   - source text is non-empty, and
   - target text is empty or starts with `TRANSLATION_ERROR`.
8. Exact source text matches in `NAME_TERM_TRANSLATIONS` are translated locally.
9. Other rows are batched into prompt lines with their line number, speaker, and source text.
10. API translations and dictionary translations are merged back into the pending row list.
11. The chosen translation is cleaned/wrapped, assigned to the `translated text` cell, and the workbook is saved to `OUT/` using the original filename.
12. If processing raises unexpectedly after the workbook is considered saveable, an already-existing output file is left untouched so previously translated lines are not overwritten by partial work.

## Translation Request Flow

`request_translations_from_api()` builds one batch prompt for all non-dictionary rows in a workbook.

Inputs:

- Source and target languages from `TranslatorConfig`.
- Character speaking styles from `CHARACTER_SPEAKING_STYLES`.
- Per-row formatted lines from `LINE_FORMAT_TEMPLATE`.
- Prompt rules from `TRANSLATION_PROMPT_TEMPLATE`.

External call:

- `translate_batch_with_gemini()` creates a Gemini client via `get_client()`.
- If `AI_STUDIO_API_KEY` is set in `.env`, the client uses Google AI Studio.
- Otherwise, if `GOOGLE_CLOUD_PROJECT` is set, the client uses Vertex AI with configured shared/flex request headers.
- If neither credential path is configured, client creation raises an error.

Response parsing:

- Successful responses are expected as raw lines like `Line 12: translated text`.
- A regex extracts line numbers and translation bodies into `{line_number: translated_text}`.
- If Gemini raises or returns an empty response, `translator.py` returns a `BATCH_TRANSLATION_ERROR: ...` string.

## Translation Selection Rules

For every pending workbook row, the script selects output in this order:

1. Use `NAME_TERM_TRANSLATIONS` if the source text was an exact dictionary match.
2. Use the batch error string if the Gemini request failed.
3. Use the parsed Gemini translation for that line number.
4. Write `PARSING_ERROR: Line N missing.` when the API response did not contain the expected line.

This makes failures visible in the workbook instead of silently leaving cells blank.

## Formatting Flow

All selected translations pass through `wrap_text(translated_text, file_name, message_type)` before being written to Excel.

`wrap_text()` does three things:

1. Calls `clean_text()` to strip model-added wrapping quotes, normalize punctuation, and remove trailing periods from choices.
2. Calls `resolve_wrap_params()` to choose wrapping rules from `FormattingConfig`.
3. Wraps the text either with `textwrap.fill()` or with `wrap_per_line_limits()` for configured per-line choice limits.

Important formatting rules:

- Files starting with `adv_unit_` skip width-based wrapping.
- `choice` rows use choice-specific limits and join wrapped lines with `" \n"` so Excel renders spacing correctly.
- Dialogue message types, currently `message` and `messagelog`, are capped by dialogue line-break settings.
- Other rows use the default max character width and no line-count cap unless configured otherwise.

## Configuration Surface

| Concern | Where | Current values |
| --- | --- | --- |
| Source language | `TranslatorConfig.SOURCE_LANGUAGE` | `Japanese` |
| Target language | `TranslatorConfig.TARGET_LANGUAGE` | `English` |
| Input folder | `TranslatorConfig.SOURCE_FOLDER_PATH` | `IN` |
| Output folder | `TranslatorConfig.OUTPUT_FOLDER_PATH` | `OUT` |
| Required source header | `ExcelConfig.SOURCE_HEADER` | `text` |
| Required target header | `ExcelConfig.TARGET_HEADER` | `translated text` |
| Optional speaker header | `ExcelConfig.SPEAKER_HEADER` | `translated name` |
| Optional message type header | `ExcelConfig.TYPEMESSAGE_HEADER` | `type` |
| Gemini model | `ModelConfig.GEMINI_MODEL` | `gemini-3-flash-preview` |
| API Studio credential | `.env` | `AI_STUDIO_API_KEY` |
| Vertex credential switch | `.env` | `GOOGLE_CLOUD_PROJECT` |

## Error and Skip Behavior

| Situation | Behavior | Why |
| --- | --- | --- |
| `IN/` does not exist | Prints an error and returns zero processed files. | Avoids creating or guessing source data. |
| No `.xlsx` files in `IN/` | Prints `No Excel files found.` and returns zero. | Treats empty input as a no-op. |
| Workbook has no active sheet | Skips the workbook. | There is no sheet to read or write. |
| Source header not found in first ten rows | Skips the workbook. | The script cannot identify source rows safely. |
| Target header missing | Skips the workbook. | There is nowhere to write translations. |
| Gemini call fails | Writes the batch error string into each pending non-dictionary row. | Makes API failure visible in output cells. |
| Gemini response omits a line | Writes a parsing error for that line. | Flags response-shape drift or prompt-following failures. |
| One workbook raises unexpectedly | Logs the exception and continues with the next workbook. If the matching output file already existed before this run, it is not overwritten by partial in-memory changes. | Batch processing should not stop because one file failed, and crashes should not remove already translated lines. |

## Why the Architecture Is Shaped This Way

- Excel files are the system boundary. The project does not maintain a database or intermediate artifact format because the source and output contract is already `.xlsx`.
- Translation is batched per workbook to reduce API overhead and give Gemini more context across adjacent lines.
- Exact dictionary translations run before the API to preserve canonical names/terms and avoid spending tokens on deterministic substitutions.
- Speaker styles are injected into every batch prompt so the model can adapt tone without needing separate calls per character.
- Formatting is performed after translation so both dictionary and model outputs follow the same game UI constraints.
- Errors are written into output cells because the workbook is the review surface for translators/editors.

## Current Boundaries and Coupling

- `process_excel_files.py` is the central coordinator and currently contains both orchestration and response parsing.
- `translator.py` is the only module that should know about `google.genai`.
- `formatting.py` depends on `FormattingConfig` and `text_utils.clean_text()`, but does not know about Excel.
- `dictionary.py` and `character_styles.py` are static data sources.
- `config.py` imports prompt system instructions for Gemini generation config, so model configuration is coupled to prompt content.

## Extension Points

- Add more canonical names or terms in `dictionary.py`.
- Add or adjust character voice guidance in `character_styles.py`.
- Tune prompt behavior in `prompts.py`.
- Change model, language, folder, header, or wrapping constants in `config.py`.
- Add support for additional sheets by changing `process_workbook()` from `workbook.active` to an explicit sheet iteration strategy.
- Add concurrent workbook processing around `process_excel_files_in_folder()`, but keep API rate limits in mind.
- Move response parsing out of `process_excel_files.py` if prompt formats or parsers become more complex.
