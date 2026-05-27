import os
from dataclasses import dataclass

from google.genai import types as genai_types
from google.genai.types import ThinkingConfig, ThinkingLevel

from Models import TranslationResponse
from prompts import TRANSLATION_SYSTEM_INSTRUCTIONS


@dataclass(frozen=True, slots=True)
class ModelConfig:
    gemini_model = "gemini-3.5-flash"

    # Model Temperature - for Gemini 3 series, keep it at 1.0, for older models try 0.1-0.3
    temp = 1.0

    # Low thinking halves the quality of instruction following, so we set it to Medium
    thinking_level = ThinkingConfig(thinking_level=ThinkingLevel.MEDIUM)

    # Used with Vertex AI, helps with rate-limiting errors and halves the costs
    flex_mode = genai_types.HttpOptions(
        headers={
            "X-Vertex-AI-LLM-Request-Type": "shared",
            "X-Vertex-AI-LLM-Shared-Request-Type": "flex",
        }
    )

    generation_config = genai_types.GenerateContentConfig(
        temperature=temp,
        system_instruction=TRANSLATION_SYSTEM_INSTRUCTIONS,
        response_mime_type="application/json",
        response_schema=TranslationResponse,
        thinking_config=thinking_level,
    )

    @staticmethod
    def is_vertex_ai() -> bool:
        # TODO: Find a better way to detect Vertex AI
        vertex_project = os.getenv("GOOGLE_CLOUD_PROJECT", None)
        return True if vertex_project else False


class TranslatorConfig:
    # Language settings
    TARGET_LANGUAGE = "English"
    SOURCE_LANGUAGE = "Japanese"

    # xlsx files paths
    SOURCE_FOLDER_PATH = "IN"
    OUTPUT_FOLDER_PATH = "OUT"

    # Translation error messages
    TRANSLATION_ERROR_SIGN = "TRANSLATION_ERROR:"
    EMPTY_RESPONSE_ERROR = f"{TRANSLATION_ERROR_SIGN} API returned empty response."
    MISSING_LINE_NUMBER_ERROR = f"{TRANSLATION_ERROR_SIGN} API didn't return this line number."

    # Parallel file processing and Gemini retry/rate-limit controls.
    MAX_PARALLEL_FILES = 3
    GEMINI_TPM_LIMIT = 200_000
    GEMINI_MAX_RETRIES = 8
    GEMINI_RETRY_BASE_DELAY_SECONDS = 2.0
    GEMINI_RETRY_MAX_DELAY_SECONDS = 120.0
    GEMINI_TOKEN_ESTIMATE_CHARS_PER_TOKEN = 3


class ExcelConfig:
    # Headers for the source and target columns
    SOURCE = "text"
    TARGET = "translated text"
    # Header for the speaker identification column
    ORIGINAL_SPEAKER = "name"
    TRANSLATED_SPEAKER = "translated name"
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


class ReplacementConfig:
    # Dash-like sequences/characters normalized to ―― or ―
    DOUBLE_DASH_REPLACEMENT = "――"
    DOUBLE_DASH_REPLACEMENTS = dict.fromkeys(("--", "ーー", "——", "──"), DOUBLE_DASH_REPLACEMENT)

    SINGLE_DASH_REPLACEMENT = "―"
    SINGLE_DASH_REPLACEMENTS = dict.fromkeys(("ー", "—", "─"), SINGLE_DASH_REPLACEMENT)

    INTERPUNCTION_REPLACEMENTS = {"。": ".", "…": "...", "~": "～"}
