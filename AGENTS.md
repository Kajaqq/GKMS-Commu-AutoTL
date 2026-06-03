# Repository Guidelines
## Project Structure & Module Organization

This is a small Python excel file translation tool. It reads input `.xlsx` files from `IN/`, translates their contents using Gemini API, and writes the translated output to `OUT/`.

Source modules live at the repository root:

- `process_excel_files.py`: main orchestration for reading workbooks, selecting rows, translating, formatting, and saving output.
- `ai/translator.py`: lazy `google-genai` client setup, token counting, rate-limit acquisition, and API calls.
- `ai/utils.py`: local Gemini request/token/day rate limiters and translation exceptions.
- `ai/Models.py`: dataclass prompt models and Pydantic response models used for structured Gemini output validation.
- `config/config.py`: env-driven model/tier/retry config, folder paths, fixed Excel header, wrapping, safety, and Gemini generation constants.
- `config/prompts.py`: system instruction, batch prompt template, and per-line format.
- `utils/translator_helper.py`: prompt reference filtering and Pydantic-backed translation response parsing.
- `config/character_styles.py`, `config/dictionary.py`: character voice guidance and canonical term/name translations.
- `utils/formatting.py`, `utils/text_utils.py`: output cleanup, layout helpers, cell normalization, and punctuation/quote normalization.
- `IN/`: input `.xlsx` files. `OUT/`: generated translated `.xlsx` files.
- `.agents/Architecture.md`: current architecture notes, dataflow, extension points, and important invariants.

There is currently no dedicated `tests/` directory.

## Architecture & Dataflow Notes

The current architecture is documented in `.agents/Architecture.md`. Read it before changing workbook flow, Gemini integration, prompt construction, response validation, or formatting behavior.

Runtime flow:

1. `process_excel_files_in_folder()` finds `IN/*.xlsx`, creates `OUT/`, creates one shared `GeminiTranslationClient`, and processes files with `ThreadPoolExecutor`.
2. `WorkbookTranslator.process()` loads the active sheet, validates the fixed first-row header, collects untranslated rows, translates them, writes formatted target cells, and saves the output workbook.
3. `collect_rows()` only sends rows whose `text` is non-empty and whose `translated text` is empty or starts with `TRANSLATION_ERROR`. Merged target cells are skipped.
4. `get_prompt_references()` includes only glossary entries and character styles relevant to the current batch.
5. `TranslationPrompt.__str__()` renders the prompt templates from `config/prompts.py`.
6. `GeminiTranslationClient.translate_batch()` uses `google-genai`, local token/request/day limiters, configured retry/timeout options, and JSON structured output.
7. `parse_translation_response()` validates Gemini JSON with `TranslationResponse`, fills missing/empty translations with `TRANSLATION_ERROR:`, and returns translations keyed by workbook line number.
8. `wrap_text()` cleans and wraps translations according to file name and message type before writing cells.
9. The batch summary reports failed files and files saved with `TRANSLATION_ERROR`; the CLI exits non-zero when either occurred.

## Build, Test, and Development Commands

- `uv sync`: install project dependencies from `pyproject.toml`.
- `uv run process_excel_files.py`: run the translator over `IN/*.xlsx` and write results to `OUT/`.
- `uv run python -m py_compile process_excel_files.py`: quick syntax/import sanity check for the main script.
- `uv run ruff check .`: run configured Ruff lint checks.
- `uv run ty check`: run the configured type checker.
- `run.bat`: Windows convenience wrapper around the main `uv run` command.

Avoid running the full translator unless API credentials are configured and network/API usage is intended.

## Coding Style & Naming Conventions

Use Python 3.14-compatible code. Follow the existing style: 4-space indentation, descriptive snake_case functions and variables, and PascalCase config classes. Ruff is configured in `pyproject.toml` with a 120-character line length.

Keep modules focused by responsibility instead of adding unrelated logic to `process_excel_files.py`. The main workbook flow currently assumes a fixed first-row header layout: `type`, `name`, `translated name`, `text`, `translated text`. Preserve that contract unless the change explicitly updates the workbook format and architecture documentation.

Gemini responses are expected as JSON matching the `TranslationResponse` Pydantic model in `ai/Models.py`; do not reintroduce ad hoc text parsing for normal translation responses. Use `utils.translator_helper.parse_translation_response()` so duplicate, unexpected, missing, and empty lines stay visible as validation errors or `TRANSLATION_ERROR:` cell values.

The project uses the modern `google-genai` SDK. Do not replace it with legacy Gemini/Vertex SDKs. `ai/translator.py` lazily creates `genai.Client(http_options=ModelConfig.retry_options)` and lets the SDK resolve authentication/backend settings from the environment. `.env.sample` documents `GEMINI_API_KEY` for AI Studio, optional `GOOGLE_GENAI_USE_ENTERPRISE=True` for the enterprise/ADC path, `PAID_TIER` for local quota tier selection, and `GOOGLE_GENAI_USE_FLEX_MODE` for flex service tier behavior.

Prefer using modern Python features and libraries like:
- `typing` for type annotations.
- `dataclasses` for data classes.
- `Pathlib` for file paths
- `openpyxl` for Excel file reading and writing.
- `pydantic` for data validation and serialization.

If writing async code use:
- `aiofiles` for async file I/O.
- `aiohttp` for HTTP calls.
- `winloop` for the async event loop

Keep comments short and useful; avoid restating obvious code.

## Testing Guidelines

No formal test framework is configured yet. For changes to workbook flow, add focused tests if introducing a test suite, using names like `test_process_workbook_skips_missing_header`.

At minimum, run:

```bash
uv run python -m py_compile process_excel_files.py
uv run ruff check process_excel_files.py
uv run ty check process_excel_files.py
```

For broader code changes, also run:

```bash
uv run ruff check .
uv run ty check .
```

For formatting changes, validate against a small workbook in `IN/` and inspect the generated file in `OUT/`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Refactor Configuration, move secrets to '.env'` and `Revamp character speaking styles.` Keep commit messages concise and describe the user-visible or architectural change.

Pull requests should include: what changed, why it changed, how it was tested, and any impact on `.env`, Gemini credentials, `IN/`, or `OUT/` files.

## Security & Configuration Tips

Do not commit real API credentials. Use `.env` for `GEMINI_API_KEY`; enterprise/Google Cloud credentials should come from the surrounding environment rather than committed files. `.env.sample` documents the API-key variable and optional tier/backend variables currently expected by the repo. Treat generated `OUT/` files as review artifacts, not source-of-truth configuration.
