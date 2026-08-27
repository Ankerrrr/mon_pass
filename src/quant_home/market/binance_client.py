from collections.abc import Callable
import time
from typing import Any

import httpx


class BinancePublicClient:
    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        max_attempts: int = 3,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def exchange_info(self) -> dict[str, Any]:
        return self._get_json("/api/v3/exchangeInfo")

    def _get_json(self, path: str) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            try:
                response = self.client.get(path)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Binance response must be a JSON object")
                return payload
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
                if not retryable or attempt + 1 >= self.max_attempts:
                    raise
                retry_after = (
                    exc.response.headers.get("Retry-After")
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None
                )
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                self.sleep(delay)
        raise RuntimeError("unreachable")
