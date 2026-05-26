from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field
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

class TranslationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    translations: list[TranslatedLine] = Field(description="One translated item for each source item.")
