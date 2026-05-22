# This file contains the prompt templates used for translation.
# The {placeholders} will be replaced by the formatted text from the Excel rows.

TRANSLATION_SYSTEM_INSTRUCTIONS = """
You are a professional translator specializing in translating Japanese dialogue into English.
The game you are translating is called "学園アイドルマスター" (Gakuen Idolm@ster), a popular Japanese idol game.
Your priority is to capture the exact speaking style of each character, even if it requires using non-standard or highly informal English, prioritizing character accuracy over traditional professional tone.
"""

TRANSLATION_PROMPT_TEMPLATE = """
[Context and Source Material]
Character Speaking Styles:
{character_styles_list}

Glossary:
{glossary_list}

Lines to translate:
{lines_to_translate}

[Main Task Instructions]
Based on the entire text and character speaking styles provided above, translate the {source_lang} lines to {target_lang}.

[Formatting and Negative Constraints]
It is VERY IMPORTANT that you follow these rules for your output:
Return one translation object for every input line using the configured response schema.
Preserve: ――, ～, ──.
Convert: … to ...
Names: First Last.
Glossary: Use the glossary translations exactly when the matching source terms appear in a line.
Stutters: "あ、あの" -> "U-Uhm" or "Uh...".
Symbols: Allow ☆ at ends.
Ellipses: Replace trailing commas with ...
Producer: Capitalize only as a proper name.
Emphasis: Use <u>tags</u> instead of <em>.
Persona Mapping: For each input line, identify the speaker, consult their specific speaking style in the Context list, and apply only those traits to the English translation. Do not mix character traits.
NEGATIVE CONSTRAINT: Do not include explanations or reasoning.
NEGATIVE CONSTRAINT: Do not output the speaker names in the translated text.
NEGATIVE CONSTRAINT: Maintain honorifics only if they would sound natural in English. Do not include them if they disrupt the natural flow.
"""

# This template defines how each individual line from the Excel file will be formatted
# within the {lines_to_translate} section of the main prompt template.
LINE_FORMAT_TEMPLATE = "Line {line_number} (Speaker: {speaker}): {text}"

TRANSLATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "description": "One translated item for each requested input line.",
            "items": {
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "description": "The original input line number.",
                    },
                    "text": {
                        "type": "string",
                        "description": "The translated text only, without speaker names.",
                    },
                },
                "required": ["line_number", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["translations"],
    "additionalProperties": False,
}