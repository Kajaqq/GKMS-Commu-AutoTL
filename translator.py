import os
import random
import threading
import time

from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors, Client

from config import ModelConfig, TranslatorConfig

# ---  Exceptions Setup ---
class GeminiTranslationError(RuntimeError):
    pass
class GeminiDailyQuotaExhaustedError(GeminiTranslationError):
    pass
class EmptyGeminiResponseError(GeminiTranslationError):
    pass

# --- API Setup ---
load_dotenv()
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
    def __init__(self, limit: int, refill_period_seconds: float = 60.0) -> None:
        self._capacity = float(limit)
        self._tokens = float(limit)
        self._refill_rate = self._capacity / refill_period_seconds
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
class DailyRequestLimiter:
    def __init__(self, requests_per_day: int) -> None:
        self._limit = requests_per_day
        self._used = 0
        self._timezone = ZoneInfo("America/Los_Angeles")
        self._reset_at = _next_pacific_midnight(self._timezone)
        self._condition = threading.Condition()

    def acquire(self) -> None:
        if self._limit <= 0:
            return

        with self._condition:
            self._reset_if_needed()
            if self._used < self._limit:
                self._used += 1
                return

            raise GeminiDailyQuotaExhaustedError(
                f"Local Gemini RPD limit of {self._limit} requests reached. "
                f"Requests per day reset at {self._reset_at.isoformat()}."
            )

    def _reset_if_needed(self) -> None:
        now = datetime.now(self._timezone)
        if now < self._reset_at:
            return

        self._used = 0
        self._reset_at = _next_pacific_midnight(self._timezone)
# ---------------------------------------------------------------------------------------------------------
def _next_pacific_midnight(tz: ZoneInfo) -> datetime:
    tomorrow = datetime.now(tz).date() + timedelta(days=1)
    return datetime.combine(tomorrow, dt_time.min, tzinfo=tz)
def _estimate_tokens(prompt_text: str, chars_per_token: int) -> int:
    chars_per_token = max(1, chars_per_token)
    return max(1, len(prompt_text) // chars_per_token)
def _require_response_text(response) -> str:
    response_text = getattr(response, "text", None)
    if response_text:
        return response_text
    raise EmptyGeminiResponseError("Empty response from the Gemini API.")
def _response_input_token_count(response) -> int:
    usage_metadata = getattr(response, "usage_metadata", None)
    return getattr(usage_metadata, "prompt_token_count", 0)
def _retry_delay(attempt: int, is_rate_limit: bool) -> float:
    exponent = attempt + 1 if is_rate_limit else attempt
    delay_seconds = min(
        TranslatorConfig.GEMINI_RETRY_BASE_DELAY_SECONDS * (2 ** exponent),
        TranslatorConfig.GEMINI_RETRY_MAX_DELAY_SECONDS,
    )
    return delay_seconds * random.uniform(0.75, 1.25)
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
def _is_daily_quota_error(error: Exception) -> bool:
    error_text = str(error).lower()
    daily_quota_terms = (
        "requests per day",
        "request limit per day",
        "per day per project",
        "daily quota",
        "quota duration: 1 day",
        "quota duration: 1 days",
        " rpd",
    )
    return any(term in error_text for term in daily_quota_terms)
def _is_retryable_error(error: Exception) -> bool:
    if isinstance(error, EmptyGeminiResponseError):
        return True
    if _is_daily_quota_error(error):
        return False
    status_code = _get_status_code(error)
    if status_code in {408, 409, 429, 500, 502, 503, 504}:
        return True
    return isinstance(error, genai_errors.ServerError | TimeoutError | ConnectionError)
def _retry_after_seconds(error: Exception) -> float | None:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None)
    retry_after = headers.get("retry-after") if headers else None
    if not retry_after:
        return None

    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
# ---------------------------------------------------------------------------------------------------------
def print_debug(batch_prompt, model_name, generation_config):
    print(
        f"--- Debugging Info ---\n"
        f"Model: {model_name}\n"
        f"Temperature: {generation_config.temperature}\n"
        f"System Instruction:\n{generation_config.system_instruction}\n"
        f"Batch prompt:\n{batch_prompt}"
    )
def get_client() -> genai.Client:
    api_key = os.getenv("AI_STUDIO_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    if ModelConfig.is_vertex_ai():
        return genai.Client(vertexai=True, http_options=ModelConfig.flex_mode)
    raise ValueError("No API key or Vertex AI Project provided")

class GeminiTranslationClient:
    def __init__(
            self,
            model_name: str = ModelConfig.gemini_model,
            debug: bool = False,
    ) -> None:
        self._client: genai.Client | None = None
        self._client_lock = threading.Lock()
        self._model_name = model_name
        self._debug = debug
        self._global_cooldown = GlobalCooldown()
        self._request_limiter = (
            TokenBucketRateLimiter(TranslatorConfig.GEMINI_RPM_LIMIT)
            if TranslatorConfig.GEMINI_RPM_LIMIT > 0
            else None
        )
        self._input_token_limiter = (
            TokenBucketRateLimiter(TranslatorConfig.GEMINI_TPM_LIMIT)
            if TranslatorConfig.GEMINI_TPM_LIMIT > 0
            else None
        )
        self._daily_request_limiter = (
            DailyRequestLimiter(TranslatorConfig.GEMINI_RPD_LIMIT)
            if TranslatorConfig.GEMINI_RPD_LIMIT > 0
            else None
        )

    def translate_batch(self, batch_prompt) -> str:
        """Calls Gemini with one workbook-sized translation prompt."""
        prompt_text = str(batch_prompt)
        estimated_input_tokens = _estimate_tokens(
            prompt_text,
            TranslatorConfig.GEMINI_TOKEN_ESTIMATE_CHARS_PER_TOKEN,
        )
        generation_config = ModelConfig.generation_config

        if self._debug:
            print_debug(prompt_text, self._model_name, generation_config)

        for attempt in range(TranslatorConfig.GEMINI_MAX_RETRIES + 1):
            self._global_cooldown.wait_if_active()
            self._acquire_rate_limits(estimated_input_tokens)

            try:
                response = self._get_client().models.generate_content(
                    model=self._model_name,
                    contents=prompt_text,
                    config=generation_config,
                )
                response_text = _require_response_text(response)

                actual_input_tokens = _response_input_token_count(response)
                if self._input_token_limiter and actual_input_tokens > 0:
                    self._input_token_limiter.update_actual(estimated_input_tokens, actual_input_tokens)

                return response_text.strip()
            except Exception as error:
                is_rate_limit = _is_rate_limit_error(error)
                is_retryable = _is_retryable_error(error)
                error_message = f"{type(error).__name__}: {error}"

                if _is_daily_quota_error(error):
                    raise GeminiDailyQuotaExhaustedError(
                        f"Gemini daily quota is exhausted and will not recover by retrying: {error_message}"
                    ) from error

                if not is_retryable:
                    raise GeminiTranslationError(f"Non-retryable Gemini API error: {error_message}") from error

                if attempt == TranslatorConfig.GEMINI_MAX_RETRIES:
                    raise GeminiTranslationError(
                        f"Gemini API error after {TranslatorConfig.GEMINI_MAX_RETRIES + 1} attempts: {error_message}"
                    ) from error

                delay_seconds = _retry_delay(attempt, is_rate_limit)
                retry_after_seconds = _retry_after_seconds(error)
                if retry_after_seconds is not None:
                    delay_seconds = max(delay_seconds, retry_after_seconds)
                if is_rate_limit:
                    self._global_cooldown.trigger(delay_seconds)

                retry_type = "rate limit" if is_rate_limit else "retryable"
                print(
                    f"Gemini {retry_type} error on attempt {attempt + 1}: "
                    f"{error_message}. Retrying in {delay_seconds:.1f}s..."
                )
                time.sleep(delay_seconds)

        raise GeminiTranslationError("Gemini retry loop ended unexpectedly.")

    def _acquire_rate_limits(self, estimated_input_tokens: int) -> None:
        if self._request_limiter:
            self._request_limiter.acquire(1)
        if self._input_token_limiter:
            self._input_token_limiter.acquire(estimated_input_tokens)
        if self._daily_request_limiter:
            self._daily_request_limiter.acquire()

    def _get_client(self) -> Client:
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is None:
                self._client = get_client()
            return self._client
