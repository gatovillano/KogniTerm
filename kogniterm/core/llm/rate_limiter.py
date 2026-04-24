import time
from collections import deque
import tiktoken
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, rate_limit_calls: int = 5, rate_limit_period: int = 60):
        self.rate_limit_calls = rate_limit_calls
        self.rate_limit_period = rate_limit_period
        self.call_timestamps = deque()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")

    def wait_if_needed(self):
        """Bloquea hasta que el rate limit permita otra llamada."""
        current_time = time.time()
        while self.call_timestamps and self.call_timestamps[0] <= current_time - self.rate_limit_period:
            self.call_timestamps.popleft()

        if len(self.call_timestamps) >= self.rate_limit_calls:
            time_to_wait = self.rate_limit_period - (current_time - self.call_timestamps[0])
            if time_to_wait > 0:
                logger.info(f"Rate limit alcanzado. Esperando {time_to_wait:.1f}s...")
                time.sleep(time_to_wait)
        
        self.call_timestamps.append(time.time())

    def get_token_count(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            return len(text) // 4
