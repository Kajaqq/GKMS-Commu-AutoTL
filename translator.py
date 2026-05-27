import os
import random
import threading
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

from config import ModelConfig, TranslatorConfig

# --- API Setup ---
load_dotenv()
USING_VERTEX_AI = ModelConfig.is_vertex_ai()
GEMINI_API_KEY = os.getenv("AI_STUDIO_API_KEY", None)
AI_MODEL = ModelConfig.gemini_model


class GeminiTranslationError(RuntimeError):
    pass


class EmptyGeminiResponseError(GeminiTranslationError):
    pass


@dataclass(frozen=True, slots=True)
class GeminiRetryConfig:
    max_retries: int = TranslatorConfig.GEMINI_MAX_RETRIES
    base_delay_seconds: float = TranslatorConfig.GEMINI_RETRY_BASE_DELAY_SECONDS
    max_delay_seconds: float = TranslatorConfig.GEMINI_RETRY_MAX_DELAY_SECONDS


class GlobalCooldown:
    def __init__(self) -> None:
        self._active_until = 0.0
        self._condition = threading.Condition()

    def wait_if_active(self) -> None:
        with self._condition:
            while True:
                remaining_seconds = self._active_until - time.monotonic()
                if remaining_seconds <= 0:
                    return
                self._condition.wait(timeout=remaining_seconds)

    def trigger(self, delay_seconds: float) -> None:
        with self._condition:
            self._active_until = max(self._active_until, time.monotonic() + delay_seconds)
            self._condition.notify_all()


class TokenBucketRateLimiter:
    def __init__(self, tokens_per_minute: int) -> None:
        self._capacity = float(tokens_per_minute)
        self._tokens = float(tokens_per_minute)
        self._refill_rate = self._capacity / 60.0
        self._updated_at = time.monotonic()
        self._condition = threading.Condition()

    def acquire(self, token_count: int) -> None:
        if self._capacity <= 0:
            return

        requested_tokens = min(max(float(token_count), 1.0), self._capacity)
        with self._condition:
            while True:
                self._refill()
                if self._tokens >= requested_tokens:
                    self._tokens -= requested_tokens
                    return

                wait_seconds = (requested_tokens - self._tokens) / self._refill_rate
                self._condition.wait(timeout=wait_seconds)

    def update_actual(self, estimated_tokens: int, actual_tokens: int) -> None:
        if self._capacity <= 0:
            return

        with self._condition:
            self._refill()
            self._tokens = min(self._capacity, self._tokens + estimated_tokens - actual_tokens)
            self._condition.notify_all()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed_seconds = now - self._updated_at
        if elapsed_seconds <= 0:
            return

        self._tokens = min(self._capacity, self._tokens + elapsed_seconds * self._refill_rate)
        self._updated_at = now


def get_client() -> genai.Client:
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


def _estimate_tokens(prompt_text: str) -> int:
    chars_per_token = max(1, TranslatorConfig.GEMINI_TOKEN_ESTIMATE_CHARS_PER_TOKEN)
    return max(1, len(prompt_text) // chars_per_token)


def _get_status_code(error: Exception) -> int | None:
    code = getattr(error, "code", None)
    if isinstance(code, int):
        return code

    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    return None


def _is_rate_limit_error(error: Exception) -> bool:
    if _get_status_code(error) == 429:
        return True

    error_text = str(error).lower()
    return any(term in error_text for term in ("rate limit", "quota", "resource_exhausted"))


def _is_retryable_error(error: Exception) -> bool:
    if isinstance(error, EmptyGeminiResponseError):
        return True

    status_code = _get_status_code(error)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True

    return isinstance(error, genai_errors.ServerError | TimeoutError | ConnectionError)


def _retry_delay(attempt: int, is_rate_limit: bool, retry_config: GeminiRetryConfig) -> float:
    exponent = attempt + 1 if is_rate_limit else attempt
    delay_seconds = min(
        retry_config.base_delay_seconds * (2**exponent),
        retry_config.max_delay_seconds,
    )
    return delay_seconds * random.uniform(0.75, 1.25)


def _response_token_count(response) -> int:
    usage_metadata = getattr(response, "usage_metadata", None)
    if usage_metadata is None:
        return 0

    total_tokens = getattr(usage_metadata, "total_token_count", 0)
    if total_tokens:
        return total_tokens

    prompt_tokens = getattr(usage_metadata, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage_metadata, "candidates_token_count", 0) or 0
    return prompt_tokens + completion_tokens


def _require_response_text(response) -> str:
    response_text = response.text if response else None
    if not response_text:
        raise EmptyGeminiResponseError("Empty response from the Gemini API for file.")
    return response_text


class GeminiTranslationClient:
    def __init__(
        self,
        model_name: str = AI_MODEL,
        debug: bool = False,
        retry_config: GeminiRetryConfig | None = None,
        tpm_limit: int = TranslatorConfig.GEMINI_TPM_LIMIT,
    ) -> None:
        self._client: genai.Client | None = None
        self._client_lock = threading.Lock()
        self._model_name = model_name
        self._debug = debug
        self._retry_config = retry_config or GeminiRetryConfig()
        self._global_cooldown = GlobalCooldown()
        self._rate_limiter = TokenBucketRateLimiter(tpm_limit) if tpm_limit > 0 else None

    def translate_batch(self, batch_prompt) -> str:
        """Calls Gemini with one workbook-sized translation prompt."""
        prompt_text = str(batch_prompt)
        estimated_tokens = _estimate_tokens(prompt_text)
        generation_config = ModelConfig.generation_config

        if self._debug:
            print_debug(prompt_text, self._model_name, generation_config)

        for attempt in range(self._retry_config.max_retries + 1):
            self._global_cooldown.wait_if_active()
            if self._rate_limiter:
                self._rate_limiter.acquire(estimated_tokens)

            try:
                response = self._get_client().models.generate_content(
                    model=self._model_name,
                    contents=prompt_text,
                    config=generation_config,
                )
                response_text = _require_response_text(response)

                actual_tokens = _response_token_count(response)
                if self._rate_limiter and actual_tokens > 0:
                    self._rate_limiter.update_actual(estimated_tokens, actual_tokens)

                return response_text.strip()
            except Exception as error:
                is_rate_limit = _is_rate_limit_error(error)
                is_retryable = _is_retryable_error(error)
                error_message = f"{type(error).__name__}: {error}"

                if not is_retryable:
                    raise GeminiTranslationError(f"Non-retryable Gemini API error: {error_message}") from error

                if attempt == self._retry_config.max_retries:
                    raise GeminiTranslationError(
                        f"Gemini API error after {self._retry_config.max_retries + 1} attempts: {error_message}"
                    ) from error

                delay_seconds = _retry_delay(attempt, is_rate_limit, self._retry_config)
                if is_rate_limit:
                    self._global_cooldown.trigger(delay_seconds)

                retry_type = "rate limit" if is_rate_limit else "retryable"
                print(
                    f"Gemini {retry_type} error on attempt {attempt + 1}: "
                    f"{error_message}. Retrying in {delay_seconds:.1f}s..."
                )
                time.sleep(delay_seconds)

        raise GeminiTranslationError("Gemini retry loop ended unexpectedly.")

    def _get_client(self) -> genai.Client:
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is None:
                self._client = get_client()
            return self._client


def translate_batch_with_gemini(batch_prompt, model_name=AI_MODEL, debug=False):
    """Calls the Gemini API client with a single batch prompt."""
    try:
        return GeminiTranslationClient(model_name=model_name, debug=debug).translate_batch(batch_prompt)
    except GeminiTranslationError as error:
        print(f"Error translating batch: {error}")
        return f"BATCH_TRANSLATION_ERROR: {error}"
