"""Connectivity checks used by Quick Setup.

Every function returns a :class:`Result` and never raises: the wizard shows the
message instead of a traceback. Timeouts are short - the wizard must stay
responsive when a provider is offline.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

USER_AGENT = "ASTA-Setup/0.1"
DEFAULT_TIMEOUT = 8.0
DISCORD_HOSTS = ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com")


@dataclass
class Result:
    ok: bool
    label: str
    detail: str = ""
    optional: bool = False
    data: Dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if self.ok and self.optional:
            return "optional"
        return "ok" if self.ok else "fail"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "label": self.label,
            "detail": self.detail,
            "optional": self.optional,
            "status": self.status,
        }


def _get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = DEFAULT_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        status = response.status
    try:
        return status, json.loads(raw.decode("utf-8"))
    except ValueError:
        return status, {}


# -- Discord ---------------------------------------------------------------
def validate_discord_webhook(url: Optional[str]) -> Result:
    value = (url or "").strip()
    if not value:
        return Result(False, "Discord webhook", "empty - paste the webhook URL")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in DISCORD_HOSTS:
        return Result(False, "Discord webhook", "must be an https://discord.com/api/webhooks/... URL")
    if "/api/webhooks/" not in parsed.path:
        return Result(False, "Discord webhook", "URL has no /api/webhooks/<id>/<token> path")
    try:
        status, payload = _get_json(value)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            return Result(False, "Discord webhook", "rejected by Discord ({}): wrong or revoked URL".format(exc.code))
        return Result(False, "Discord webhook", "Discord answered HTTP {}".format(exc.code))
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        return Result(False, "Discord webhook", "unreachable: {}".format(exc))
    channel = str(payload.get("channel_id") or "")
    name = str(payload.get("name") or "webhook")
    return Result(
        True,
        "Discord webhook",
        "connected to #{} ({})".format(name, channel[:6] + "…" if channel else "unknown channel"),
        data={"name": name, "channelId": channel},
    )


# -- Providers -------------------------------------------------------------
def validate_binance(base_url: str = "https://api.binance.com") -> Result:
    root = (base_url or "https://api.binance.com").rstrip("/")
    try:
        _get_json(root + "/api/v3/ping", timeout=6)
        _, ticker = _get_json(root + "/api/v3/ticker/price?symbol=BTCUSDT", timeout=6)
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        return Result(False, "Binance", "unreachable: {}".format(exc))
    price = ticker.get("price")
    return Result(True, "Binance", "BTCUSDT = {}".format(price) if price else "ping ok")


def validate_yahoo(base_url: str = "https://query1.finance.yahoo.com") -> Result:
    root = (base_url or "https://query1.finance.yahoo.com").rstrip("/")
    url = root + "/v8/finance/chart/AAPL?range=1d&interval=1d"
    try:
        _get_json(url, timeout=6)
    except (urllib.error.URLError, socket.timeout, OSError, ValueError) as exc:
        return Result(False, "Yahoo Finance", "unreachable: {}".format(exc))
    return Result(True, "Yahoo Finance", "chart endpoint ok (AAPL)")


def validate_mt5(terminal_url: Optional[str], token: Optional[str] = None) -> Result:
    value = (terminal_url or "").strip()
    if not value:
        return Result(
            True,
            "MT5 terminal",
            "not configured - forex uses public market data",
            optional=True,
        )
    parsed = urllib.parse.urlparse(value)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        return Result(
            False,
            "MT5 terminal",
            "no listener on {}:{} ({}) - start the MT5 MCP bridge or leave it blank".format(host, port, exc),
        )
    return Result(
        True,
        "MT5 terminal",
        "port {}:{} reachable{}".format(host, port, " (token set)" if token else ""),
    )


def validate_oanda(api_token: Optional[str], account_id: Optional[str] = None,
                   base_url: str = "https://api-fxpractice.oanda.com") -> Result:
    token = (api_token or "").strip()
    if not token:
        return Result(True, "OANDA", "not configured (optional)", optional=True)
    try:
        status, payload = _get_json(
            base_url.rstrip("/") + "/v3/accounts",
            headers={"Authorization": "Bearer {}".format(token)},
            timeout=8,
        )
    except urllib.error.HTTPError as exc:
        return Result(False, "OANDA", "rejected (HTTP {})".format(exc.code))
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        return Result(False, "OANDA", "unreachable: {}".format(exc))
    accounts = payload.get("accounts") or []
    wanted = (account_id or "").strip()
    if wanted and accounts and wanted not in {a.get("id") for a in accounts}:
        return Result(False, "OANDA", "account {} not visible to this token".format(wanted))
    return Result(True, "OANDA", "token valid - {} account(s)".format(len(accounts) or "?"))


# -- Local system ----------------------------------------------------------
def validate_port(host: str, port: int, probe_running: bool = True) -> Result:
    """Free port = ok. In use = fail, unless something answers as an ASTA dashboard."""
    host = host or "127.0.0.1"
    try:
        with socket.create_connection((host, int(port)), timeout=1.5):
            in_use = True
    except OSError:
        in_use = False
    if not in_use:
        return Result(True, "Port {}".format(port), "free on {}".format(host))
    if probe_running:
        try:
            status, payload = _get_json("http://{}:{}/api/health".format(host, port), timeout=2)
            if payload.get("status") == "ok":
                return Result(
                    True,
                    "Port {}".format(port),
                    "another ASTA dashboard is already running (pid {})".format(payload.get("pid")),
                )
        except (urllib.error.URLError, socket.timeout, OSError, ValueError):
            pass
    return Result(False, "Port {}".format(port), "already used by another process")


def validate_database_path(path: str) -> Result:
    target = Path(path).expanduser()
    try:
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / ".asta-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Result(False, "Database path", "not writable: {}".format(exc))
    exists = target.exists()
    return Result(
        True,
        "Database path",
        "{} ({:.1f} KB)".format("existing" if exists else "will be created", target.stat().st_size / 1024 if exists else 0),
        data={"path": str(target), "exists": exists},
    )


def validate_all(
    env: Dict[str, str],
    providers: Optional[Dict[str, Dict[str, Any]]] = None,
    database_path: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 4310,
) -> Dict[str, list]:
    """Run every check the final step shows. Returns ``{"webhooks": [...], "providers": [...], "local": [...]}``."""
    providers = providers or {}
    webhooks = [
        validate_discord_webhook(env.get("DISCORD_WEBHOOK_FOREX")),
        validate_discord_webhook(env.get("DISCORD_WEBHOOK_CRYPTO")),
        validate_discord_webhook(env.get("DISCORD_WEBHOOK_STOCK")),
    ]
    provider_checks = []
    crypto = (providers.get("crypto") or {}).get("type", "binance")
    if crypto == "binance":
        provider_checks.append(validate_binance((providers.get("crypto") or {}).get("base_url", "")))
    stock = (providers.get("stock") or {}).get("type", "yahoo")
    if stock == "yahoo":
        provider_checks.append(validate_yahoo((providers.get("stock") or {}).get("base_url", "")))
    forex = (providers.get("forex") or {}).get("type", "mt5")
    if forex == "mt5":
        provider_checks.append(validate_mt5(env.get("MT5_TERMINAL_URL"), env.get("MT5_TERMINAL_TOKEN")))
    elif forex == "oanda":
        provider_checks.append(validate_oanda(env.get("OANDA_API_TOKEN"), env.get("OANDA_ACCOUNT_ID")))

    local = [validate_port(host, port)]
    if database_path:
        local.append(validate_database_path(database_path))
    return {
        "webhooks": [item.as_dict() for item in webhooks],
        "providers": [item.as_dict() for item in provider_checks],
        "local": [item.as_dict() for item in local],
    }
