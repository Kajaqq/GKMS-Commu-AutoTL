import os
from abc import ABC

from google.genai import types as genai_types

from prompts import TRANSLATION_SYSTEM_INSTRUCTIONS


class ModelConfig(ABC):
    GEMINI_MODEL = "gemini-3-flash-preview"

    # Model Temperature - for Gemini 3 series, keep it at 1.0, for older models try 0.1-0.3
    TEMPERATURE = 1.0

    # System Instructions to use
    SYSTEM_INSTRUCTIONS = TRANSLATION_SYSTEM_INSTRUCTIONS

    # Used with Vertex AI, helps with rate-limiting errors
    flex_mode = genai_types.HttpOptions(
        headers={
            "X-Vertex-AI-LLM-Request-Type": "shared",
            "X-Vertex-AI-LLM-Shared-Request-Type": "flex",
        }
    )

    # Disable blocking content that the API deems 'unsafe'
    BLOCK_NONE = genai_types.HarmBlockThreshold.BLOCK_NONE
    safety_config = [
        genai_types.SafetySetting(
            category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=BLOCK_NONE,
        ),
        genai_types.SafetySetting(
            category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=BLOCK_NONE,
        ),
        genai_types.SafetySetting(
            category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=BLOCK_NONE,
        ),
    ]
    generation_config = genai_types.GenerateContentConfig(
        temperature=TEMPERATURE,
        system_instruction=SYSTEM_INSTRUCTIONS,
        safety_settings=safety_config,
        thinking_config=genai_types.ThinkingConfig(
            thinking_level=genai_types.ThinkingLevel.MINIMAL
        ),
    )

    @staticmethod
    def is_vertex_ai() -> bool:
        vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT", None)
        return True if vertex_project else False


class TranslatorConfig:
    # Language settings
    TARGET_LANGUAGE = "English"
    SOURCE_LANGUAGE = "Japanese"

    # xlsx files paths
    SOURCE_FOLDER_PATH = "IN"
    OUTPUT_FOLDER_PATH = "OUT"


class ExcelConfig:
    # Headers for the source and target columns
    SOURCE = "text"
    TARGET = "translated text"
    # Header for the speaker identification column
    SPEAKER = "translated name"
    # Header for the message type column
    TYPE = "type"

class FormattingConfig:
    # Default character width for general text wrapping
    DEFAULT_MAX_CHARS_PER_LINE = 40

    # Message types treated as dialogue (subject to dialogue line-break limit)
    DIALOGUE_TYPES = ["message", "messagelog"]
    DEFAULT_MAX_DIALOGUE_LINE_BREAKS = 4

    # File-name prefixes that trigger special rules
    ADV_PEVENT_PREFIX = "adv_pevent_002_"
    ADV_UNIT_PREFIX = "adv_unit_"  # adv_unit_ skips width-based wrapping

    # Single-line/bubble choice rules for adv_pevent_ files.
    # Fallback width when per-line limits are not set.
    ADV_PEVENT_MAX_CHARS = 29
    ADV_PEVENT_MAX_CHOICE_BREAKS = 3

    # Per-line limits for adv_pevent_ choices; set to None to use ADV_PEVENT_MAX_CHARS instead.
    ADV_PEVENT_CHOICE_LINE1_CHARS = None
    ADV_PEVENT_CHOICE_LINE2_CHARS = None
    ADV_PEVENT_CHOICE_LINE3_CHARS = None

    # Bubble-choice rules for non-adv_pevent_ files (approx. 34 full-width / 43 half-width)
    OTHER_MAX_CHARS = 43
    OTHER_MAX_CHOICE_BREAKS = 3
