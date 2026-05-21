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
