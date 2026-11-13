"""HTTP client and provider contract shared by every market."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Dict, List, Optional

import httpx

from asta.core.signal_model import Candle, Market
from asta.utils.exceptions import ConfigurationError, ProviderError
from asta.utils.logger import get_logger
from asta.utils.time_utils import ensure_utc, normalize_timeframe, timeframe_to_seconds, utcnow

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class BaseHttpClient:
    """Thin httpx wrapper: retries, backoff, rate-limit handling, JSON decoding."""

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 15.0,
        max_attempts: int = 3,
        backoff_seconds: float = 0.5,
        headers: Optional[Dict[str, str]] = None,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = float(timeout)
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = float(backoff_seconds)
        self.headers = {"User-Agent": "ASTA/0.1", **(headers or {})}
        self._client = client
        self._owns_client = client is None
        self.logger = get_logger("asta.http.{}".format(type(self).__name__))

    @property
    def http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout, headers=self.headers)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    def __enter__(self) -> "BaseHttpClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- requests ---------------------------------------------------------
    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return "{}/{}".format(self.base_url, path.lstrip("/"))

    def request_json(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = self._url(path)
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            retry_after: Optional[float] = None
            try:
                response = self.http.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                last_error = ProviderError("request failed: {}".format(exc), url=url)
            else:
                if response.status_code in RETRYABLE_STATUS:
                    last_error = ProviderError(
                        "HTTP {} on retryable response".format(response.status_code),
                        url=url,
                        body=response.text[:200],
                    )
                    retry_after = self._retry_after(response)
                elif response.status_code >= 400:
                    raise ProviderError(
                        "HTTP {} from provider".format(response.status_code),
                        url=url,
                        body=response.text[:300],
                    )
                else:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise ProviderError("provider returned non-JSON payload", url=url) from exc

            if attempt == self.max_attempts:
                break
            delay = retry_after if retry_after is not None else self.backoff_seconds * (2 ** (attempt - 1))
            time.sleep(min(max(delay, 0.0), 30.0))
        raise last_error or ProviderError("request failed", url=url)

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


class MarketDataProvider(ABC):
    """Fetches OHLCV candles for one market.

    Implementations must return closed candles sorted oldest -> newest with
    timezone-aware UTC timestamps, and raise :class:`ProviderError` otherwise.
    """

    market: Market
    name: str = ""
    default_base_url: str = ""
    health_symbol: Optional[str] = None

    def __init__(self, settings: Optional[Dict[str, Any]] = None, client: Optional[BaseHttpClient] = None):
        self.settings: Dict[str, Any] = dict(settings or {})
        self.timeout = float(self.settings.get("timeout_seconds", 15))
        self.client: BaseHttpClient = client or self.build_client()
        self.logger = get_logger("asta.provider.{}".format(self.name or type(self).__name__))

    # -- lifecycle --------------------------------------------------------
    @property
    def base_url(self) -> str:
        return str(self.settings.get("base_url") or self.default_base_url).rstrip("/")

    def build_client(self) -> BaseHttpClient:
        return BaseHttpClient(
            base_url=self.base_url,
            timeout=self.timeout,
            max_attempts=int(self.settings.get("max_attempts", 3)),
            backoff_seconds=float(self.settings.get("backoff_seconds", 0.5)),
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "MarketDataProvider":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- contract ---------------------------------------------------------
    @abstractmethod
    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        """Return up to ``limit`` closed candles for ``symbol``."""

    def is_configured(self) -> bool:
        return True

    def health_check(self) -> bool:
        if not self.is_configured():
            return False
        if not self.health_symbol:
            return True
        try:
            return bool(self.fetch_candles(self.health_symbol, "1h", 10))
        except Exception as exc:  # noqa: BLE001 - health must never raise
            self.logger.warning("health check failed", extra={"error": str(exc)})
            return False

    # -- helpers ----------------------------------------------------------
    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    def validate_timeframe(self, timeframe: str) -> str:
        return normalize_timeframe(timeframe)

    @staticmethod
    def filter_closed_candles(candles: List[Candle], timeframe: str, now=None) -> List[Candle]:
        """Drop trailing bars that are still forming.

        Exchanges return the in-progress bar as the last row (Binance klines,
        Yahoo chart). Scanners must never evaluate a bar whose close can still
        change.
        """
        if not candles:
            return []
        now = now or utcnow()
        seconds = timeframe_to_seconds(timeframe)
        closed = list(candles)
        while closed and (ensure_utc(closed[-1].timestamp) + timedelta(seconds=seconds)) > now:
            closed.pop()
        return closed

    def _require_config(self, keys: List[str]) -> None:
        missing = [key for key in keys if not self.settings.get(key)]
        if missing:
            raise ConfigurationError(
                "{} provider missing settings: {}".format(self.name, ", ".join(missing)),
                provider=self.name,
            )
