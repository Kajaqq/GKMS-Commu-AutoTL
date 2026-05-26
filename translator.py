import os

from dotenv import load_dotenv
from google import genai

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


def print_debug(batch_prompt, model_name, generation_config):
    print(
        f"--- Debugging Info ---\n"
        f"Model: {model_name}\n"
        f"Temperature: {generation_config.temperature}\n"
        f"System Instruction:\n{generation_config.system_instruction}\n"
        f"Batch prompt:\n{batch_prompt}"
    )

def translate_batch_with_gemini(batch_prompt, model_name=AI_MODEL, debug=False):
    """Calls the Gemini API client with a single batch prompt."""
    client = get_client()
    generation_config = ModelConfig.generation_config
    if debug:
        print_debug(batch_prompt, model_name, generation_config)
    try:
        response = client.models.generate_content(model=model_name, contents=batch_prompt, config=generation_config)
        if not response or not response.text:
            message = "Empty response from the Gemini API for file"
            print(f"Error translating batch: {message}")
            return f"BATCH_TRANSLATION_ERROR: {message}"
        else:
            return response.text.strip()
    except Exception as e:
        print(f"Error translating batch: {e}")
        return f"BATCH_TRANSLATION_ERROR: {e}"
