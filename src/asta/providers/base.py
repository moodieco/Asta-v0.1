"""Provider contract + retrying HTTP helper."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from asta.core.signal_model import Candle, Market
from asta.utils.exceptions import AstaError, ConfigurationError, ProviderError
from asta.utils.logger import get_logger
from asta.utils.time_utils import normalize_timeframe

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class MarketDataProvider(ABC):
    """Fetches OHLCV candles for one market.

    Implementations must return candles sorted oldest -> newest, all timestamps
    timezone-aware UTC, and raise :class:`ProviderError` on failure.
    """

    market: Market
    name: str = ""
    default_base_url: str = ""
    health_symbol: Optional[str] = None

    def __init__(self, settings: Optional[Dict[str, Any]] = None, client: Optional[httpx.Client] = None):
        self.settings: Dict[str, Any] = dict(settings or {})
        self.base_url: str = str(self.settings.get("base_url") or self.default_base_url).rstrip("/")
        self.timeout = float(self.settings.get("timeout_seconds", 15))
        self.max_attempts = max(1, int(self.settings.get("max_attempts", 3)))
        self.backoff_seconds = float(self.settings.get("backoff_seconds", 0.5))
        self._client = client
        self._owns_client = client is None
        self.logger = get_logger("asta.provider.{}".format(self.name or type(self).__name__))

    # -- lifecycle --------------------------------------------------------
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={"User-Agent": "ASTA/0.1 (+https://github.com/asta)"},
            )
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    def __enter__(self) -> "MarketDataProvider":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- contract ---------------------------------------------------------
    @abstractmethod
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        """Return up to ``limit`` closed candles for ``symbol``."""

    def is_configured(self) -> bool:
        """Whether credentials/base url are present. Default: yes."""
        return True

    def health_check(self) -> bool:
        if not self.is_configured():
            return False
        if not self.health_symbol:
            return True
        try:
            candles = self.fetch_candles(self.health_symbol, "1h", 10)
            return bool(candles)
        except AstaError as exc:
            self.logger.warning("health check failed", extra={"error": str(exc)})
            return False

    # -- helpers ----------------------------------------------------------
    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    def validate_timeframe(self, timeframe: str) -> str:
        return normalize_timeframe(timeframe)

    def _request_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        last_error: Optional[AstaError] = None
        for attempt in range(1, self.max_attempts + 1):
            retry_after: Optional[float] = None
            try:
                response = self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                last_error = ProviderError(
                    "request failed: {}".format(exc), provider=self.name, url=url
                )
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = ProviderError(
                        "HTTP {} on retryable response".format(response.status_code),
                        provider=self.name,
                        url=url,
                        body=response.text[:200],
                    )
                    retry_after = self._retry_after(response)
                elif response.status_code >= 400:
                    raise ProviderError(
                        "HTTP {} from provider".format(response.status_code),
                        provider=self.name,
                        url=url,
                        body=response.text[:300],
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ProviderError(
                            "provider returned non-JSON payload",
                            provider=self.name,
                            url=url,
                        ) from exc

            if attempt == self.max_attempts:
                break
            delay = retry_after if retry_after is not None else self.backoff_seconds * (2 ** (attempt - 1))
            time.sleep(min(max(delay, 0.0), 30.0))
            self.logger.debug(
                "retrying provider request",
                extra={"provider": self.name, "attempt": attempt, "delay": round(delay, 2)},
            )
        raise last_error or ProviderError("request failed", provider=self.name, url=url)

    @staticmethod
    def _retry_after(response: httpx.Response) -> Optional[float]:
        header = response.headers.get("Retry-After")
        if header:
            try:
                return float(header)
            except ValueError:
                pass
        try:
            payload = response.json()
        except ValueError:
            return None
        if isinstance(payload, dict):
            for key in ("retry_after", "retryAfter"):
                if key in payload:
                    try:
                        return float(payload[key])
                    except (TypeError, ValueError):
                        return None
        return None

    def _require_config(self, keys: List[str]) -> None:
        missing = [key for key in keys if not self.settings.get(key)]
        if missing:
            raise ConfigurationError(
                "{} provider missing credentials: {}".format(self.name, ", ".join(missing)),
                provider=self.name,
            )
