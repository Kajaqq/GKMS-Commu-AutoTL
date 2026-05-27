from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from prompts import TRANSLATION_PROMPT_TEMPLATE, LINE_FORMAT_TEMPLATE


@dataclass(frozen=True, slots=True)
class PromptReferences:
    """
    Reference material included in a translation prompt.

    Attributes:
        glossary_entries: Glossary terms and canonical translations.
        character_styles: Character-specific voice and style instructions.
    """

    glossary_entries: list[str]
    character_styles: list[str]


@dataclass(frozen=True, slots=True)
class SourceLine:
    """
    A single source line prepared for translation.

    Attributes:
        line_number: Original workbook line number.
        speaker: Name of the character speaking in the line
        text: Source text to translate.
    """

    line_number: int
    speaker: str
    text: str

    def __str__(self) -> str:
        """
        Formats the source line for inclusion in the model prompt.

        Returns:
            Line formatted with `LINE_FORMAT_TEMPLATE`.
        """

        return LINE_FORMAT_TEMPLATE.format(
            line_number=self.line_number,
            speaker=self.speaker,
            text=self.text,
        )


@dataclass(frozen=True, slots=True)
class TranslationPrompt:
    """
    A complete prompt sent to the API

    Attributes:
        references: Glossary and character style context
        lines: Source lines to translate in this batch.
        source_lang: Source language
        target_lang: Target language
    """

    references: PromptReferences
    lines: list[SourceLine]
    source_lang: str
    target_lang: str

    def __str__(self) -> str:
        """
        Formats the prompt text sent to the translation model.

        Returns:
            The full prompt formatted with `TRANSLATION_PROMPT_TEMPLATE`.
        """

        return TRANSLATION_PROMPT_TEMPLATE.format(
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            character_styles_list="\n".join(self.references.character_styles),
            glossary_list="\n".join(self.references.glossary_entries),
            lines_to_translate="\n".join(str(line) for line in self.lines),
        )


class TranslatedLine(BaseModel):
    """
    Model for a single translated line.

    Attributes:
        line_number: Original input line number this translation belongs to.
        text: Translated text without speaker names.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    line_number: int = Field(description="The original input line number.")
    text: str = Field(description="The translated text only, without speaker names.")

    @field_validator("text", mode="after")
    @classmethod
    def strip_text_quotes(cls, value: str) -> str:
        """
        Removes wrapping triple quotes or code fences from translated text.
        """

        # Strip triple quotes if they exist
        value = value.strip()
        unwanted_quotes = ("```", '"""', "'''")
        if value.startswith(unwanted_quotes) and value.endswith(unwanted_quotes):
            return value[3:-3]
        return value


class TranslationResponse(BaseModel):
    """
    Model for the Translation response sent as `response_schema` to the API
    Includes validation logic for line numbers

    Attributes:
        translations: Translated lines format that should be returned.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    translations: list[TranslatedLine] = Field(description="One translated item for each source item.")

    @model_validator(mode="after")
    def validate_line_numbers(self, info: ValidationInfo[set[int] | None]) -> Self:
        """
        Validate if the number of lines sent to the API,
        match the number of lines received

        Args:
            info: Pydantic validation info containing the expected line numbers as a set
                in `context`.

        Returns:
            The validated response instance.

        Raises:
            ValueError: If a returned line number is duplicated or unexpected.
        """

        #
        expected_lines = info.context
        if expected_lines is None:
            # Gemini API can attempt validation on its own,
            # without access to the expected_lines set, so we skip it.
            return self
        seen_lines: set[int] = set()
        for item in self.translations:
            line_number = item.line_number
            if line_number in seen_lines:
                raise ValueError(f"API returned duplicate translation for line {line_number}.")
            seen_lines.add(line_number)

            if line_number not in expected_lines:
                raise ValueError(f"API returned unexpected line {line_number}.")
        return self
