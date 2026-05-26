from typing import Any

from pydantic import ValidationError

from character_styles import CHARACTER_SPEAKING_STYLES
from dictionary import NAME_TERM_TRANSLATIONS
from Models import PromptReferences, SourceLine, TranslationResponse

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

def get_prompt_refrences(source_lines: list[SourceLine]) -> PromptReferences:
    """Returns a `PromptReferences` object containing references to glossary entries and character styles."""
    character_names = {line.speaker for line in source_lines if line.speaker}
    source_text = "\n".join(line.text for line in source_lines)

    return PromptReferences(
        glossary_entries=[
            f"{term}: {translation}"
            for term, translation in NAME_TERM_TRANSLATIONS.items()
            if term in source_text
        ],
        character_styles=[
            f"{name}: {style}"
            for name, style in CHARACTER_SPEAKING_STYLES.items()
            if any(character_name in name for character_name in character_names)
        ],
    )


def parse_translation_response(response_text: str, expected_line_numbers: list[int]) -> dict[int, str]:
    try:
        response = TranslationResponse.model_validate_json(response_text)
    except ValidationError as error:
        raise ValueError(f"Gemini response did not match translation schema: {error}") from error

    expected_lines = set(expected_line_numbers)
    parsed_translations: dict[int, str] = {}
    for item in response.translations:
        line_number = item.line_number
        text = item.text.strip()

        if line_number not in expected_lines:
            raise ValueError(f"Gemini returned unexpected line {line_number}.")

        if line_number in parsed_translations:
            raise ValueError(f"Gemini returned duplicate translation for line {line_number}.")

        if not text:
            raise ValueError(f"Gemini returned empty translation for line {line_number}.")

        parsed_translations[line_number] = text

    missing_lines = sorted(expected_lines - parsed_translations.keys())
    if missing_lines:
        raise ValueError(f"Gemini response missing lines: {missing_lines}.")

    return parsed_translations
