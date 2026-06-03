from google.genai.types import GenerateContentConfig, HttpOptions, HttpRetryOptions, ThinkingConfig, ThinkingLevel

from ai.Models import TranslationResponse
from config.prompts import TRANSLATION_SYSTEM_INSTRUCTIONS


class ModelConfig:
    gemini_model = "gemini-3.5-flash"

    # Model Temperature - for Gemini 3 series, keep it at 1.0, for older models try 0.1-0.3
    temp = 1.0

    # Low thinking halves the quality of instruction following, so we set it to Medium
    thinking_level = ThinkingConfig(thinking_level=ThinkingLevel.MEDIUM)

    generation_config = GenerateContentConfig(
        temperature=temp,
        system_instruction=TRANSLATION_SYSTEM_INSTRUCTIONS,
        response_mime_type="application/json",
        response_schema=TranslationResponse,
        thinking_config=thinking_level,
    )

    # Rate limit configs
    # These defaults are based on conservative Google AI Studio limits,
    # it is recommended to check your limits and set them here.
    GEMINI_RPM_LIMIT = 10
    GEMINI_TPM_LIMIT = 250_000
    GEMINI_RPD_LIMIT = 250

    class RetryConfig:
        # Use to enable Flex Mode Billing for Vertex AI API calls.
        flex_mode = False
        flex_mode_headers = {"X-Vertex-AI-LLM-Request-Type": "shared", "X-Vertex-AI-LLM-Shared-Request-Type": "flex"}
        # Response timeout for the API call in milliseconds.
        timeout = 120 * 1000
        # Max retries for the API call.
        max_attempts = 5
        # Exponential backoff config for retries.
        initial_delay = 1.0
        max_delay = 60.0
        exp_base = 2.0
        jitter = 1.0
        # HTTP status codes to retry on.
        http_status_codes = [408, 429, 500, 502, 503, 504]

        http_options = HttpOptions(
            headers=flex_mode_headers if flex_mode else None,
            timeout=timeout,
            retry_options=HttpRetryOptions(
                initial_delay=initial_delay,
                attempts=max_attempts,
                max_delay=max_delay,
                exp_base=exp_base,
                jitter=jitter,
                http_status_codes=http_status_codes,
            ),
        )


class TranslatorConfig:
    # Language settings
    TARGET_LANGUAGE = "English"
    SOURCE_LANGUAGE = "Japanese"

    # xlsx files paths
    SOURCE_FOLDER_PATH = "IN"
    OUTPUT_FOLDER_PATH = "OUT"

    # Set to true to translate based on dict if the line only contains a single term.
    # If True, if source_text = key in `NAME_TERM_TRANSLATIONS' translated_text = value
    # This skips sending the line to the API, and can cause loss of context/quality for weaker models.
    REPLACE_SINGLE_TERM = False

    # Translation error messages
    TRANSLATION_ERROR_SIGN = "TRANSLATION_ERROR:"
    EMPTY_RESPONSE_ERROR = f"{TRANSLATION_ERROR_SIGN} API returned empty response."
    MISSING_LINE_NUMBER_ERROR = f"{TRANSLATION_ERROR_SIGN} API didn't return this line number."

    # How many file can be translated at once
    MAX_PARALLEL_FILES = 5


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
