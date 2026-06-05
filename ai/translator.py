import threading
import warnings

from google import genai
from google.genai.local_tokenizer import LocalTokenizer

from config.config import ModelConfig
from ai.utils import TranslationErrors, TokenBucketRateLimiter, DailyRequestLimiter


# ---------------------------------------------------------------------------------------------------------
GeminiQuotaError = TranslationErrors.GeminiQuotaError
GeminiDailyQuotaExhaustedError = TranslationErrors.GeminiDailyQuotaExhaustedError
GeminiEmptyResponseError = TranslationErrors.GeminiEmptyResponseError

def get_token_count(prompt):
    tokenizer = LocalTokenizer(model_name="gemini-3-pro-preview")
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The SDK's local tokenizer implementation is experimental and may change in the future.*",
        )
        token_count = tokenizer.count_tokens(prompt)
    prompt_tokens = token_count.total_tokens
    if not token_count or not prompt_tokens:
        import math
        chars_per_token = 4
        prompt_tokens = math.ceil(len(prompt) / chars_per_token)
    return prompt_tokens

def print_debug(batch_prompt, model_name, generation_config):
    print(
        f"--- Debugging Info ---\n"
        f"Model: {model_name}\n"
        f"Temperature: {generation_config.temperature}\n"
        f"System Instruction:\n{generation_config.system_instruction}\n"
        f"Batch prompt:\n{batch_prompt}"
    )
# ---------------------------------------------------------------------------------------------------------

class GeminiTranslationClient:
    def __init__(self, debug=False, model_name=ModelConfig.gemini_model, gen_config=ModelConfig.generation_config) -> None:
        self.client: genai.Client | None = None
        self.model_name = model_name
        self.gen_config = gen_config
        self.retry_options = ModelConfig.retry_options
        self.debug = debug
        self._client_lock = threading.Lock()
        self._fallback_lock = threading.Lock()
        self._fallback_models = list(ModelConfig.fallback_models)
        self._set_rate_limiters(model_name)

    def translate_batch(self, batch_prompt) -> str:
        """Calls Gemini with one workbook-sized translation prompt."""
        prompt_text = str(batch_prompt)
        client = self._get_client()
        input_token_count = get_token_count(prompt_text)
        model_name = self._acquire_rate_limits(input_token_count)
        if self.debug:
            print_debug(prompt_text, model_name, self.gen_config)

        response = client.models.generate_content(
                model=model_name,
                contents=prompt_text,
                config=self.gen_config,
        )

        if response.text is not None:
            return response.text
        else:
            raise GeminiEmptyResponseError("No response text returned from Gemini API")

    def _acquire_rate_limits(self, input_tokens: int) -> str:
        while True:
            model_name = self.model_name
            try:
                self._input_token_limiter.validate_capacity(input_tokens)
                self._daily_request_limiter.acquire()
                self._request_limiter.acquire(1)
                self._input_token_limiter.acquire(input_tokens)
            except GeminiDailyQuotaExhaustedError as error:
                if not self._switch_to_fallback_model(error, model_name):
                    raise
            else:
                return model_name

    def _set_rate_limiters(self, model_name: str) -> None:
        rpm_limit, tpm_limit, rpd_limit = ModelConfig._get_rate_limits(model_name, ModelConfig.usage_tier)
        self._request_limiter = TokenBucketRateLimiter(rpm_limit)
        self._input_token_limiter = TokenBucketRateLimiter(tpm_limit)
        self._daily_request_limiter = DailyRequestLimiter(rpd_limit)

    def _switch_to_fallback_model(self, error: GeminiDailyQuotaExhaustedError, exhausted_model: str) -> bool:
        with self._fallback_lock:
            if self.model_name != exhausted_model:
                return True

            while self._fallback_models:
                fallback_model = self._fallback_models.pop(0)
                if fallback_model == self.model_name:
                    continue

                answer = input(f"{error}\nUse fallback model {fallback_model}? [y/N]: ").strip().lower()
                if answer not in {"y", "yes"}:
                    continue

                self.model_name = fallback_model
                self._set_rate_limiters(fallback_model)
                print(f"Switched to fallback model: {fallback_model}")
                return True

            return False

    def _get_client(self) -> genai.Client:
        if self.client is not None:
            return self.client

        with self._client_lock:
            if self.client is None:
                self.client = genai.Client(http_options=self.retry_options)
            return self.client
