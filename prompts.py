# --- prompts.py ---
# This file contains the prompt templates used for translation.

# This template defines the overall structure of the batched prompt.
# It includes instructions, character styles, and placeholders for the lines to translate.
# The {lines_to_translate} placeholder will be replaced by the formatted text from the Excel rows.
# We instruct Gemini to output in a specific format using line markers.
# Condense instructions to save tokens while keeping rules clear
TRANSLATION_PROMPT_TEMPLATE = """Task: Translate {source_lang} to {target_lang}.
Rules:
- Format: "Line [num]: [translation]"
- No speaker names in output.
- Natural, human-like dialogue.
- Preserve: ――, ～, ──.
- Convert: … to ...
- Names: First Last.
- Maintain honorifics.
- Stutters: "あ、あの" -> "U-Uhm" or "Uh...".
- Symbols: Allow ☆ at ends.
- Ellipses: Replace trailing commas with ...
- Producer: Capitalize only as a proper name.
- Emphasis: Use <u>tags</u> instead of <em>.
- Localization: Omit redundant names/honorifics if unnatural in English.

Character Speaking Styles:
{character_styles_list}

Translate the following lines. For each line, output the translation prefixed with "Line [Original Line Number]: ".

{lines_to_translate}
"""

# This template defines how each individual line from the Excel file will be formatted
# within the {lines_to_translate} section of the main prompt template.
LINE_FORMAT_TEMPLATE = "Line {line_number} (Speaker: {speaker}): {text}"

# You can add other prompt templates here for different translation scenarios
# ANOTHER_PROMPT_TEMPLATE = """Your instructions here... {variables}"""
