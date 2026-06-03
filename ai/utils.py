import threading
import time

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Exceptions
class TranslationErrors:
    class GeminiQuotaError(RuntimeError):
        pass
    class GeminiDailyQuotaExhaustedError(RuntimeError):
        pass
    class GeminiEmptyResponseError(RuntimeError):
        pass

#RateLimiters
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

        self.validate_capacity(token_count)
        requested_tokens = float(token_count)

        with self._condition:
            while True:
                self._refill()
                if self._tokens >= requested_tokens:
                    self._tokens -= requested_tokens
                    return

                wait_seconds = (requested_tokens - self._tokens) / self._refill_rate
                self._condition.wait(timeout=wait_seconds)

    def validate_capacity(self, token_count: int) -> None:
        if self._capacity <= 0:
            return

        requested_tokens = float(token_count)
        if requested_tokens > self._capacity:
            raise TranslationErrors.GeminiQuotaError(
                f"Requested {int(requested_tokens)} tokens exceeds the local Gemini TPM limit of {int(self._capacity)}."
            )

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

            raise TranslationErrors.GeminiDailyQuotaExhaustedError(
                f"Local Gemini RPD limit of {self._limit} requests reached. "
                f"Requests per day reset at {self._reset_at.isoformat()}."
            )

    def _reset_if_needed(self) -> None:
        now = datetime.now(self._timezone)
        if now < self._reset_at:
            return

        self._used = 0
        self._reset_at = _next_pacific_midnight(self._timezone)

# Utils
def _next_pacific_midnight(tz: ZoneInfo = ZoneInfo("America/Los_Angeles")) -> datetime:
    tomorrow = datetime.now(tz) + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)

