from pydantic import ValidationError

from character_styles import CHARACTER_SPEAKING_STYLES
from dictionary import NAME_TERM_TRANSLATIONS
from Models import PromptReferences, SourceLine, TranslationResponse
from config import TranslatorConfig


def get_prompt_refrences(source_lines: list[SourceLine]) -> PromptReferences:
    """
    Returns a `PromptReferences` object containing glossary entries and character styles.
    """
    character_names = {line.speaker for line in source_lines if line.speaker}
    source_text = "".join(line.text for line in source_lines).replace(" ", "")

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


def parse_translation_response(response_text: str, expected_line_numbers: set[int]) -> dict[int, str]:
    """
    Validates the recieved translations and checks for empty lines.
    """

    try:
        response = TranslationResponse.model_validate_json(
            response_text,
            context=expected_line_numbers,
        )
    except ValidationError as error:
        raise ValueError(f"API response failed validation: {error}") from error

    parsed_translations: dict[int, str] = {}

    for item in response.translations:
        line_number = item.line_number
        text = item.text
        if not text:
            parsed_translations[line_number] = TranslatorConfig.EMPTY_RESPONSE_ERROR
        else:
            parsed_translations[line_number] = text

    missing_lines = sorted(expected_line_numbers - parsed_translations.keys())
    for line_number in missing_lines:
        parsed_translations[line_number] = TranslatorConfig.MISSING_LINE_NUMBER_ERROR

    return parsed_translations
