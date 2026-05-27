from dataclasses import dataclass
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from prompts import TRANSLATION_PROMPT_TEMPLATE

@dataclass(frozen=True, slots=True)
class PromptReferences:
    glossary_entries: list[str]
    character_styles: list[str]

@dataclass(frozen=True, slots=True)
class SourceLine:
    line_number: int
    speaker: str
    text: str

    def __str__(self) -> str:
        from prompts import LINE_FORMAT_TEMPLATE

        return LINE_FORMAT_TEMPLATE.format(
            line_number=self.line_number,
            speaker=self.speaker,
            text=self.text,
        )

@dataclass(frozen=True, slots=True)
class TranslationPrompt:
    references: PromptReferences
    lines: list[SourceLine]
    source_lang: str
    target_lang: str

    def __str__(self) -> str:
        return TRANSLATION_PROMPT_TEMPLATE.format(
            source_lang=self.source_lang,
            target_lang=self.target_lang,
            character_styles_list="\n".join(self.references.character_styles),
            glossary_list="\n".join(self.references.glossary_entries),
            lines_to_translate="\n".join(str(line) for line in self.lines),
        )

class TranslatedLine(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    line_number: int = Field(description="The original input line number.")
    text: str = Field(description="The translated text only, without speaker names.")

    @field_validator("text", mode="after")
    @classmethod
    def strip_text_quotes(cls, value: str) -> str:
        value = value.strip()
        unwanted_quotes = ('```','"""',"'''")
        if value.startswith(unwanted_quotes) and value.endswith(unwanted_quotes):
            return value[3:-3]
        return value

class TranslationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    translations: list[TranslatedLine] = Field(description="One translated item for each source item.")

    @model_validator(mode="after")
    def validate_line_numbers(self, info: ValidationInfo[set[int] | None]) -> Self:
        expected_lines = info.context
        if expected_lines is None:
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
