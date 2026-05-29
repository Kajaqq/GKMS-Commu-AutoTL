from config import ReplacementConfig


def strip_wrapping_quotes(text: str) -> str:
    """
    Remove surrounding quotes that models sometimes emit.
    """
    unwanted_quotes = ("```", '"""', "'''")
    if text.startswith(unwanted_quotes) and text.endswith(unwanted_quotes):
        return text[3:-3]
    return text


def normalize_punctuation(text: str) -> str:
    """
    Normalize punctation according to `config.py` settings.
    """
    for src, replacement in ReplacementConfig.SINGLE_DASH_REPLACEMENTS.items():
        text = text.replace(src, replacement)
    for src, replacement in ReplacementConfig.DOUBLE_DASH_REPLACEMENTS.items():
        text = text.replace(src, replacement)
    for src, replacement in ReplacementConfig.INTERPUNCTION_REPLACEMENTS.items():
        text = text.replace(src, replacement)
    return text


def safe_str(value) -> str:
    """
    Return a stripped string from a cell value, or empty string if None.
    """
    return str(value).strip() if value is not None else ""


def normalize_cell(value) -> str:
    return safe_str(value).lower()


def strip_whitespace(text: str) -> str:
    return "".join(text.split())


def clean_text(text: str, message_type: str) -> str:
    """
    Apply all cleanup rules.
    """
    text = strip_wrapping_quotes(text.strip())
    text = normalize_punctuation(text)
    # Choices should not end with a period
    if message_type == "choice" and text.endswith("."):
        text = text[:-1]
    return text
