import os

from google import genai
from dotenv import load_dotenv

from config import ModelConfig

# --- API Setup ---
load_dotenv()
USING_VERTEX_AI = ModelConfig.is_vertex_ai()
GEMINI_API_KEY = os.getenv("AI_STUDIO_API_KEY", None)
AI_MODEL = ModelConfig.GEMINI_MODEL


def get_client():
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
    elif USING_VERTEX_AI:
        flex_mode = ModelConfig.flex_mode
        client = genai.Client(vertexai=True, http_options=flex_mode)
    else:
        raise ValueError("No API key or Vertex AI Project provided")
    return client


def translate_batch_with_gemini(batch_prompt, model_name=AI_MODEL):
    """Calls the Gemini API client with a single batch prompt."""
    client = get_client()
    generation_config = ModelConfig.generation_config
    try:
        response = client.models.generate_content(
            model=model_name, contents=batch_prompt, config=generation_config
        )
        if response and response.text:
            return response.text.strip()
        else:
            print("WARNING: No Response from the Gemini API for file")
            return ""
    except Exception as e:
        print(f"Error translating batch: {e}")
        return f"BATCH_TRANSLATION_ERROR: {e}"
