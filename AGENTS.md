# Repository Guidelines

## Project Structure & Module Organization

This is a small Python batch translation tool. Source modules live at the repository root:

- `process_excel_files.py`: main orchestration for reading workbooks, selecting rows, translating, formatting, and saving output.
- `translator.py`: Gemini client setup and API calls.
- `config.py`: model, folder, fixed Excel header, wrapping, safety, and Gemini generation constants.
- `prompts.py`: system instruction, batch prompt template, per-line format, and JSON response schema.
- `character_styles.py`, `dictionary.py`: character voice guidance and canonical term/name translations.
- `formatting.py`, `text_utils.py`: output cleanup, layout helpers, cell normalization, and JSON translation response parsing.
- `IN/`: input `.xlsx` files. `OUT/`: generated translated `.xlsx` files.
- `.agents/Architecture.md`: higher-level dataflow and module overview.

There is currently no dedicated `tests/` directory.

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

Gemini responses are expected as JSON matching `TRANSLATION_RESPONSE_SCHEMA`; do not reintroduce ad hoc text parsing for normal translation responses.

Prefer using modern Python features and libraries like:
- `typing` for type annotations.
- `dataclasses` for data classes.
- `Pathlib` for file paths
- `openpyxl` for Excel file reading and writing.

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
```

For broader code changes, also run:

```bash
uv run ruff check .
```

For formatting changes, validate against a small workbook in `IN/` and inspect the generated file in `OUT/`.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Refactor Configuration, move secrets to '.env'` and `Revamp character speaking styles.` Keep commit messages concise and describe the user-visible or architectural change.

Pull requests should include: what changed, why it changed, how it was tested, and any impact on `.env`, Gemini credentials, `IN/`, or `OUT/` files.

## Security & Configuration Tips

Do not commit real API credentials. Use `.env` for `AI_STUDIO_API_KEY` or `GOOGLE_CLOUD_PROJECT`; `.env.sample` documents the expected variables. Treat generated `OUT/` files as review artifacts, not source-of-truth configuration.
