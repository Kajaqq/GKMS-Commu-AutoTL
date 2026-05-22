# Architecture

## Purpose

GKMS-Commu-AutoTL is a batch translator for Gakuen Idolmaster commu Excel files. It reads `.xlsx` workbooks from `IN/`, translates missing Japanese text into English with Gemini, applies game-specific cleanup and line wrapping, and writes translated workbooks to `OUT/`.

The application is intentionally a small script pipeline rather than a service. Most state lives in the workbook being processed, while configuration, prompt rules, glossary entries, character voice guidance, and formatting rules live in Python modules.

## Runtime Entry Points

| What | Where | Why |
| --- | --- | --- |
| Main Python entry point | `process_excel_files.py` | Orchestrates folder scanning, workbook loading, header validation, row selection, prompt construction, API calls, response parsing, formatting, and saving. |
| Windows convenience runner | `run.bat` | Runs `uv run process_excel_files.py` for users launching from Windows. |
| Package/dependency definition | `pyproject.toml` | Declares Python `>=3.14`, runtime dependencies, dev dependencies, and Ruff settings. |

## Module Responsibilities

| Module | What it owns | Why it exists |
| --- | --- | --- |
| `process_excel_files.py` | End-to-end workbook workflow, fixed header validation, row filtering, dynamic glossary/style selection, prompt construction, API request coordination, translation selection, and writing translated cells. | Keeps the runnable batch workflow in one coordinator while delegating API, formatting, prompt, and text utilities. |
| `translator.py` | Gemini client creation, `generate_content` API calls, optional prompt debug printing, empty-response handling, and API exception conversion. | Isolates external API setup and failure conversion from workbook logic. |
| `config.py` | Model, language, folder, Excel header, formatting, safety, Vertex flex-mode, and Gemini generation config constants. | Centralizes values that tune behavior without changing the pipeline code. |
| `prompts.py` | System instruction, batch prompt template, per-line prompt format, and JSON response schema. | Keeps model instructions and required response shape separate from Excel mechanics. |
| `character_styles.py` | Alias-rich character voice/style descriptions. | Supplies persona guidance to the translation prompt, now filtered to characters seen in the current workbook. |
| `dictionary.py` | Fixed Japanese-to-English term/name translations. | Provides exact local translations and file-scoped glossary entries for prompt guidance. |
| `formatting.py` | Text cleanup integration, line wrapping, choice/dialogue/file-prefix layout rules. | Converts raw translations into strings that fit expected game UI constraints. |
| `text_utils.py` | Cell string normalization, model-output cleanup, punctuation normalization, and JSON translation response parsing. | Shares low-level text handling between workbook processing, formatting, and response parsing. |

## Dataflow

```text
IN/*.xlsx
  -> process_excel_files_in_folder()
  -> process_workbook()
  -> active worksheet
  -> validate_header_row()
       -> requires row 1 exactly:
          type, name, translated name, text, translated text
  -> iterate rows 2..N across columns 1..5
       -> skip merged translated-text cells
       -> collect original/translated speaker names for style filtering
       -> source text non-empty and target empty or starts TRANSLATION_ERROR?
            no  -> leave row unchanged
            yes -> exact dictionary match?
                    yes -> NAME_TERM_TRANSLATIONS
                    no  -> LINE_FORMAT_TEMPLATE batch lines
                         -> collect source text for glossary filtering
  -> find_glossary_entries()
       -> include dictionary entries whose source term appears in API-bound source text
  -> build_translation_prompt()
       -> TRANSLATION_PROMPT_TEMPLATE
       -> filtered CHARACTER_SPEAKING_STYLES
       -> filtered glossary
  -> translate_batch_with_gemini()
       -> GenerateContentConfig with JSON response schema
       -> Gemini API response text
  -> parse_translation_response()
       -> JSON object with translations[]
       -> validate expected line numbers
  -> choose translated text per pending row
  -> wrap_text()
       -> clean_text()
       -> resolve_wrap_params()
       -> textwrap/per-line wrapping
  -> write target cells
  -> save OUT/<same filename>.xlsx when completed and changed,
     or when no output file exists
```

## Workbook Processing Flow

1. `process_excel_files_in_folder()` resolves the source and output folders from `TranslatorConfig`.
2. It raises `ValueError` if `IN/` does not exist, creates `OUT/` if needed, scans `IN/` for `*.xlsx`, and processes files in sorted order.
3. `process_workbook()` loads each workbook with `openpyxl` and uses only the active sheet.
4. `validate_header_row()` checks the first worksheet row against the exact normalized header sequence `type`, `name`, `translated name`, `text`, `translated text`.
5. Data rows are read from row 2 onward using the first five columns in that fixed order.
6. Rows with a merged `translated text` cell are skipped because merged cells cannot be written normally.
7. Speaker context is collected from both `name` and `translated name`; the prompt line itself uses `translated name` or `Unknown`.
8. A row is considered for translation when:
   - source text is non-empty, and
   - target text is empty or starts with `TRANSLATION_ERROR`.
9. Exact source text matches in `NAME_TERM_TRANSLATIONS` are translated locally.
10. Other rows are batched into prompt lines with their line number, speaker, and source text.
11. Before the API call, dictionary entries are filtered to only glossary terms appearing in API-bound source text, and character styles are filtered to characters whose names or aliases match workbook speaker names.
12. API translations and dictionary translations are merged back into the pending row list.
13. The chosen translation is cleaned/wrapped, assigned to the `translated text` cell, and marked as a change.
14. The workbook is saved to `OUT/` only after processing completes and either cells changed or the matching output file did not already exist.

## Translation Request Flow

`request_translations_from_api()` builds one batch prompt for all non-dictionary rows in a workbook.

Inputs:

- Source and target languages from `TranslatorConfig`.
- API-bound line numbers, speakers, and source text.
- Character speaking styles filtered by workbook speaker names through `find_character_styles()`.
- Glossary entries filtered by API-bound source text through `find_glossary_entries()`.
- Prompt rules from `TRANSLATION_PROMPT_TEMPLATE`.
- Per-row formatted lines from `LINE_FORMAT_TEMPLATE`.

External call:

- `translate_batch_with_gemini()` creates a Gemini client via `get_client()`.
- If `AI_STUDIO_API_KEY` is set in `.env`, the client uses Google AI Studio.
- Otherwise, if `GOOGLE_CLOUD_PROJECT` is set, the client uses Vertex AI with configured shared/flex request headers.
- If neither credential path is configured, client creation raises an error.
- `ModelConfig.generation_config` requests `application/json`, applies `TRANSLATION_RESPONSE_SCHEMA`, sets temperature to `1.0`, disables selected safety blocking thresholds, and leaves Gemini thinking level unspecified.

Response parsing:

- Successful responses are expected as JSON matching `TRANSLATION_RESPONSE_SCHEMA`.
- The response shape is `{ "translations": [{ "line_number": 1, "text": "..." }] }`.
- `parse_translation_response()` parses JSON, builds `{line_number: translated_text}`, warns on duplicate or empty items, and checks that received line numbers exactly match the requested API line numbers.
- If Gemini raises, returns an empty response, returns invalid JSON, or returns mismatched line numbers, the batch becomes `BATCH_TRANSLATION_ERROR: ...`.

## Translation Selection Rules

For every pending workbook row, the script selects output in this order:

1. Use `NAME_TERM_TRANSLATIONS` if the source text was an exact dictionary match.
2. Use the batch error string if the Gemini request or JSON parsing failed.
3. Use the parsed Gemini translation for that line number.
4. Write `PARSING_ERROR: Line N missing.` when no batch error occurred but the parsed response did not contain the expected line.

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
| Required headers | `ExcelConfig` | `type`, `name`, `translated name`, `text`, `translated text` in that exact order |
| Gemini model | `ModelConfig.GEMINI_MODEL` | `gemini-3-flash-preview` |
| Gemini response format | `ModelConfig.generation_config` | `application/json` using `TRANSLATION_RESPONSE_SCHEMA` |
| API Studio credential | `.env` / `translator.py` | `AI_STUDIO_API_KEY` |
| Vertex credential switch | `.env` / `translator.py` | `GOOGLE_CLOUD_PROJECT` |
| Runtime dependencies | `pyproject.toml` | `google-genai>=2.5.0`, `openpyxl>=3.1.5`, `protobuf>=7.34.1`, `python-dotenv` |
| Dev tooling | `pyproject.toml` | `ruff>=0.15.14`, `ty>=0.0.38` |

## Error and Skip Behavior

| Situation | Behavior | Why |
| --- | --- | --- |
| `IN/` does not exist | Raises `ValueError`. | Avoids creating or guessing source data. |
| No `.xlsx` files in `IN/` | Prints `Error: No Excel files found.` and returns zero. | Treats empty input as a no-op. |
| Workbook has no active sheet | Prints an error and skips the workbook. | There is no sheet to read or write. |
| Header row does not exactly match expected fixed layout | Raises `ValueError`, which the per-file loop logs before continuing with the next workbook. | The pipeline depends on fixed column positions. |
| Target cell is a `MergedCell` | Prints a warning and skips that row. | Merged cells cannot be written like normal cells. |
| Row already has a translation that does not start with `TRANSLATION_ERROR` | Leaves the row unchanged. | Avoids overwriting completed translations. |
| No translations needed and output file already exists | Leaves the existing output file unchanged. | Avoids refreshing files without content changes. |
| No translations needed and output file does not exist | Saves a workbook copy to `OUT/`. | Ensures processed input can still produce an output artifact. |
| Gemini call fails or returns empty text | Writes the batch error string into each pending non-dictionary row. | Makes API failure visible in output cells. |
| Gemini response is invalid JSON or has missing/unexpected line numbers | Writes the batch error string into each pending non-dictionary row. | Flags response-shape drift or prompt-following failures. |
| One workbook raises unexpectedly | Logs the exception and continues with the next workbook; the workbook is saved only if processing completed. | Batch processing should not stop because one file failed, and partial in-memory changes should not overwrite output. |

## Why the Architecture Is Shaped This Way

- Excel files are the system boundary. The project does not maintain a database or intermediate artifact format because the source and output contract is already `.xlsx`.
- Translation is batched per workbook to reduce API overhead and give Gemini more context across adjacent lines.
- Exact dictionary translations run before the API to preserve canonical names/terms and avoid spending tokens on deterministic substitutions.
- Glossary filtering keeps prompt context relevant by sending only dictionary entries that appear in the current API-bound source text.
- Speaker-style filtering keeps persona context focused by sending only character styles that match speakers seen in the current workbook.
- JSON schema output replaces regex parsing so response validation can check line numbers and translation fields structurally.
- Formatting is performed after translation so both dictionary and model outputs follow the same game UI constraints.
- Errors are written into output cells because the workbook is the review surface for translators/editors.

## Current Boundaries and Coupling

- `process_excel_files.py` is the central coordinator and currently contains orchestration, fixed-layout assumptions, prompt construction, and translation selection.
- `translator.py` is the only module that should know about `google.genai`.
- `config.py` imports prompt definitions for Gemini generation config, so model configuration is coupled to prompt response schema and system instructions.
- `prompts.py` defines both natural-language prompt rules and the machine-readable JSON schema expected by Gemini.
- `formatting.py` depends on `FormattingConfig` and `text_utils.clean_text()`, but does not know about Excel.
- `dictionary.py` serves two roles: exact local substitutions and prompt glossary source.
- `character_styles.py` keys include aliases, and `find_character_styles()` currently matches workbook speaker names by substring containment against those keys.

## Extension Points

- Add more canonical names or terms in `dictionary.py`; exact source-text matches become local translations, while partial matches can appear as glossary guidance.
- Add or adjust character voice guidance and aliases in `character_styles.py`.
- Tune prompt behavior or structured output shape in `prompts.py`.
- Change model, language, folder, header, or wrapping constants in `config.py`.
- Add support for non-fixed or additional sheet layouts by replacing `validate_header_row()` and the fixed `iter_rows(min_col=1, max_col=5)` assumption.
- Add concurrent workbook processing around `process_excel_files_in_folder()`, but keep API rate limits and output-file writes in mind.
- Move prompt construction or translation selection out of `process_excel_files.py` if the workbook coordinator continues to grow.
