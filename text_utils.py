import json
from typing import Any

# Dash-like sequences/characters normalized to ―― or ―
_DOUBLE_DASH_REPLACEMENTS = ("--", "ーー", "——", "──")
_SINGLE_DASH_REPLACEMENTS = ("ー", "—", "─")


def strip_wrapping_quotes(text: str) -> str:
    """Remove surrounding "..." or \"\"\"...\"\"\" that models sometimes emit."""
    if text.startswith('"""') and text.endswith('"""'):
        return text[3:-3]
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    return text


def normalize_punctuation(text: str) -> str:
    """Convert JP-style dashes, periods, ellipses, and tildes to project conventions."""
    for src in _DOUBLE_DASH_REPLACEMENTS:
        text = text.replace(src, "――")
    for src in _SINGLE_DASH_REPLACEMENTS:
        text = text.replace(src, "―")
    text = text.replace("。", ".")
    text = text.replace("…", "...")
    text = text.replace("~", "～")
    return text


def clean_text(text: str, message_type: str) -> str:
    """Apply all cleanup rules. Returns '' for empty/non-string input."""
    if not text or not isinstance(text, str):
        return ""
    text = strip_wrapping_quotes(text.strip())
    text = normalize_punctuation(text)
    # Choices should not end with a period
    if message_type == "choice" and text.endswith("."):
        text = text[:-1]
    return text


def safe_str(value: Any) -> str:
    """Returns a stripped string from a cell value, or empty string if None."""
    return str(value).strip() if value is not None else ""


def normalize_cell(value: Any) -> str:
    return safe_str(value).lower()

def parse_translation_response(response_text: str, expected_line_numbers: list[int]) -> dict[int, str]:
    try:
        payload = json.loads(response_text)
        translations = payload.get("translations")
    except json.JSONDecodeError as error:
        raise ValueError(f"Gemini returned invalid JSON: {error}") from error

    parsed_translations: dict[int, str] = {}
    for index, item in enumerate(translations, start=1):
        line_number = item.get("line_number")
        text = item.get("text").strip()
        if not isinstance(line_number, int):
             raise TypeError(f"Translation item {index} has an invalid line_number. Expected an integer. Got: {type(line_number)}")
        if not isinstance(text, str):
             raise TypeError(f"Translation item {index} has an invalid text value. Expected a string. Got: {type(text)}")
        if not text:
            print (f"WARNING: Translation item {index} has empty text. Skipping.")
            continue
        if line_number in parsed_translations:
            print(f"WARNING: Gemini returned duplicate translation for line {line_number}.")
        parsed_translations[line_number] = text

    expected_lines = set(expected_line_numbers)
    received_lines = set(parsed_translations)
    missing_lines = sorted(expected_lines - received_lines)
    unexpected_lines = sorted(received_lines - expected_lines)
    if missing_lines or unexpected_lines:
        raise ValueError(
            f"Gemini response line mismatch. "
            f"Missing Lines: {missing_lines}; "
            f"Unexpected Lines: {unexpected_lines}."
        )

    return parsed_translations