import threading

from google import genai
from google.genai.local_tokenizer import LocalTokenizer

from config.config import ModelConfig
from ai.utils import TranslationErrors, TokenBucketRateLimiter, DailyRequestLimiter


# ---------------------------------------------------------------------------------------------------------
GeminiQuotaError = TranslationErrors.GeminiQuotaError
GeminiEmptyResponseError = TranslationErrors.GeminiEmptyResponseError

def get_token_count(prompt):
    tokenizer = LocalTokenizer(model_name="gemini-3-pro-preview")
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
        self._request_limiter = TokenBucketRateLimiter(ModelConfig.GEMINI_RPM_LIMIT)
        self._input_token_limiter = TokenBucketRateLimiter(ModelConfig.GEMINI_TPM_LIMIT)
        self._daily_request_limiter = DailyRequestLimiter(ModelConfig.GEMINI_RPD_LIMIT)

    def translate_batch(self, batch_prompt) -> str:
        """Calls Gemini with one workbook-sized translation prompt."""
        prompt_text = str(batch_prompt)
        if self.debug:
            print_debug(prompt_text, self.model_name, self.gen_config)
        client = self._get_client()
        input_token_count = get_token_count(prompt_text)
        self._acquire_rate_limits(input_token_count)

        response = client.models.generate_content(
                model=self.model_name,
                contents=prompt_text,
                config=self.gen_config,
        )

        if response.text is not None:
            return response.text
        else:
            raise GeminiEmptyResponseError("No response text returned from Gemini API")

    def _acquire_rate_limits(self, input_tokens: int) -> None:
        self._input_token_limiter.acquire(input_tokens)
        self._daily_request_limiter.acquire()
        self._request_limiter.acquire(1)
        self._input_token_limiter.validate_capacity(input_tokens)

    def _get_client(self) -> genai.Client:
        if self.client is not None:
            return self.client

        with self._client_lock:
            if self.client is None:
                self.client = genai.Client(http_options=self.retry_options)
            return self.client