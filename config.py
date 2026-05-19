import os
from abc import ABC

from google.genai import types as genai_types

from prompts import TRANSLATION_SYSTEM_INSTRUCTIONS


class ModelConfig(ABC):
    GEMINI_MODEL = "gemini-3-flash-preview"
    # Model Temperature - for Gemini 3 series, keep it as 1.0, for older models try 0.1-0.3
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
    SOURCE_HEADER = "text"
    TARGET_HEADER = "translated text"

    # Header for the speaker identification column
    SPEAKER_HEADER = "translated name"

    # Header for the message type column
    TYPEMESSAGE_HEADER = "type"
