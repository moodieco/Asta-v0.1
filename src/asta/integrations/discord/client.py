"""Minimal Discord webhook client with retries and rate-limit handling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from asta.utils.exceptions import DiscordError
from asta.utils.logger import get_logger

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


@dataclass
class DeliveryResult:
    ok: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    attempts: int = 0
    dry_run: bool = False

    def __bool__(self) -> bool:
        return self.ok


class DiscordWebhookClient:
    def __init__(
        self,
        timeout: float = 10.0,
        max_attempts: int = 3,
        client: Optional[httpx.Client] = None,
        sleep=time.sleep,
    ):
        self.timeout = float(timeout)
        self.max_attempts = max(1, int(max_attempts))
        self._client = client
        self._owns_client = client is None
        self._sleep = sleep
        self.logger = get_logger("asta.discord.client")

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    @staticmethod
    def is_valid_webhook(url: Optional[str]) -> bool:
        if not url:
            return False
        return url.startswith("https://") and "/api/webhooks/" in url

    def post(self, webhook_url: str, payload: Dict[str, Any]) -> DeliveryResult:
        if not self.is_valid_webhook(webhook_url):
            return DeliveryResult(ok=False, error="invalid webhook url")

        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            delay = 0.0
            try:
                response = self.client.post(webhook_url, json=payload)
            except httpx.HTTPError as exc:
                last_error = "network error: {}".format(exc)
            else:
                if response.status_code in (200, 204):
                    return DeliveryResult(ok=True, status_code=response.status_code, attempts=attempt)
                last_error = "HTTP {}: {}".format(response.status_code, response.text[:200])
                if response.status_code not in RETRYABLE_STATUS:
                    self.logger.error("discord rejected payload", extra={"status": response.status_code})
                    return DeliveryResult(
                        ok=False, status_code=response.status_code, error=last_error, attempts=attempt
                    )
                delay = self._retry_after(response)

            if attempt < self.max_attempts:
                self._sleep(delay if delay > 0 else min(2.0 ** (attempt - 1), 10.0))

        raise DiscordError(last_error or "discord delivery failed")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
        try:
            body = response.json()
        except ValueError:
            return 0.0
        if isinstance(body, dict):
            try:
                return float(body.get("retry_after", 0.0))
            except (TypeError, ValueError):
                return 0.0
        return 0.0
