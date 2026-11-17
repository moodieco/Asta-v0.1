"""Share links: editor + view-only tokens and the LAN URLs that use them.

The dashboard binds loopback by default, but "share" exposes it to the LAN with
a token gate. Two roles:

    * editor — full access (same as sitting at the machine)
    * viewer — read-only (write endpoints answer 403)

Tokens are random ``secrets.token_urlsafe`` values persisted in ``data/share.json``.
Loopback clients (the machine owner) stay unauthenticated; anything else must
present a valid token in ``?token=``, ``X-ASTA-Token`` or ``Authorization: Bearer``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PIN_ROLES = ("viewer", "editor")
SESSION_TTL = 12 * 3600
_PIN_MIN = 4
_PIN_MAX = 64
_SCRYPT = {"n": 16384, "r": 8, "p": 1, "dklen": 32}
_PBKDF2_ITERATIONS = 600_000


def _hash_pin(pin: str, salt: bytes) -> Dict[str, Any]:
    """Derive the stored PIN digest.

    scrypt is the default, but Apple's stock python3.9 is linked against a
    LibreSSL without it, so PBKDF2-SHA256 is the portable fallback. The stored
    entry records which one produced it, and verification honours that.
    """
    material = pin.encode("utf-8")
    if hasattr(hashlib, "scrypt"):
        digest = hashlib.scrypt(material, salt=salt, **_SCRYPT)
        return {"algo": "scrypt", "params": dict(_SCRYPT), "hash": digest}
    digest = hashlib.pbkdf2_hmac("sha256", material, salt, _PBKDF2_ITERATIONS, dklen=32)
    return {"algo": "pbkdf2_sha256", "params": {"iterations": _PBKDF2_ITERATIONS}, "hash": digest}


class PinLimiter:
    """Failed-PIN backoff, per client key.

    5 misses lock the key for 60s; each further miss doubles the window up to
    15 minutes. Without this a 6-digit PIN is a few hours of brute force away.
    """

    def __init__(self, limit: int = 5, base: float = 60.0, cap: float = 900.0):
        self.limit = max(1, int(limit))
        self.base = float(base)
        self.cap = float(cap)
        self._lock = threading.Lock()
        self._state: Dict[str, Dict[str, float]] = {}

    def locked_for(self, key: str) -> int:
        now = time.time()
        with self._lock:
            entry = self._state.get(key)
            if not entry:
                return 0
            remaining = entry.get("until", 0.0) - now
            return int(remaining) + 1 if remaining > 0 else 0

    def record_failure(self, key: str) -> int:
        now = time.time()
        with self._lock:
            entry = self._state.setdefault(key, {"fails": 0.0, "until": 0.0})
            entry["fails"] += 1
            if entry["fails"] >= self.limit:
                strike = int(entry["fails"]) - self.limit
                window = min(self.base * (2 ** strike), self.cap)
                entry["until"] = now + window
                return int(window)
            return 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)



def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def lan_ips() -> List[str]:
    """Best-effort list of this machine's non-loopback IPv4 addresses."""
    ips: List[str] = []

    def add(address: str) -> None:
        if not address or address in ips:
            return
        if address.startswith("127.") or address == "::1" or address.startswith("169.254."):
            return
        if ":" in address and "." not in address:
            return  # skip bare IPv6; the dashboard is an IPv4 loopback app
        ips.append(address)

    # UDP connect trick: the kernel picks the source address for the route.
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            add(sock.getsockname()[0])
        finally:
            sock.close()
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            host = info[4][0]
            add(str(host))
    except OSError:
        pass

    return ips


class ShareManager:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self._data: Dict[str, Any] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            self._data = {"created_at": _now()}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self._data = {"created_at": _now()}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps(self._data, indent=2, sort_keys=True) + "\n"
        handle, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".share.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(body)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # -- tokens -----------------------------------------------------------
    def _ensure_tokens(self) -> None:
        # A hosted deploy (Render, Fly, ...) has no writable home for
        # data/share.json between releases, so the tokens can come from the
        # environment instead. Env always wins over the file.
        for env_name, key in (("ASTA_EDITOR_TOKEN", "editor_token"), ("ASTA_VIEWER_TOKEN", "viewer_token")):
            value = (os.environ.get(env_name) or "").strip()
            if value:
                self._data[key] = value
        if not self._data.get("editor_token"):
            self._data["editor_token"] = secrets.token_urlsafe(24)
        if not self._data.get("viewer_token"):
            self._data["viewer_token"] = secrets.token_urlsafe(24)
        self._save()

    def tokens(self) -> Dict[str, str]:
        self._ensure_tokens()
        return {"editor": self._data["editor_token"], "viewer": self._data["viewer_token"]}

    def authenticate(self, token: Optional[str]) -> Optional[str]:
        if not token:
            return None
        self._ensure_tokens()
        if secrets.compare_digest(token, self._data.get("editor_token", "")):
            return "editor"
        if secrets.compare_digest(token, self._data.get("viewer_token", "")):
            return "viewer"
        return None

    def regenerate(self) -> Dict[str, str]:
        self._data["editor_token"] = secrets.token_urlsafe(24)
        self._data["viewer_token"] = secrets.token_urlsafe(24)
        self._data["regenerated_at"] = _now()
        self._save()
        return self.tokens()

    # -- pins (role login) ------------------------------------------------
    def _pins_raw(self) -> Dict[str, Any]:
        raw = self._data.get("pins")
        pins: Dict[str, Any] = raw if isinstance(raw, dict) else {}
        self._data["pins"] = pins
        return pins

    def _pin_entry(self, role: str) -> Optional[Dict[str, Any]]:
        entry = self._pins_raw().get((role or "").strip().lower())
        return entry if isinstance(entry, dict) else None

    def set_pin(self, role: str, pin: str) -> None:
        role = (role or "").strip().lower()
        if role not in PIN_ROLES:
            raise ValueError("role must be one of {}".format(", ".join(PIN_ROLES)))
        clean = (pin or "").strip()
        if not _PIN_MIN <= len(clean) <= _PIN_MAX:
            raise ValueError("pin must be {}-{} characters".format(_PIN_MIN, _PIN_MAX))
        salt = os.urandom(16)
        derived = _hash_pin(clean, salt)
        self._pins_raw()[role] = {
            "algo": derived["algo"],
            "salt": salt.hex(),
            "hash": derived["hash"].hex(),
            "params": derived["params"],
            "updated_at": _now(),
        }
        self._save()

    def clear_pin(self, role: str) -> bool:
        role = (role or "").strip().lower()
        removed = self._pins_raw().pop(role, None) is not None
        if removed:
            self._save()
        return removed

    def pin_configured(self, role: str) -> bool:
        entry = self._pin_entry(role)
        return bool(entry and entry.get("salt") and entry.get("hash"))

    def pins_configured(self) -> Dict[str, bool]:
        return {role: self.pin_configured(role) for role in PIN_ROLES}

    def _pin_digest(self, entry: Dict[str, Any], pin: str) -> Optional[bytes]:
        try:
            salt = bytes.fromhex(str(entry.get("salt") or ""))
            raw_params = entry.get("params")
            params: Dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
            algo = str(entry.get("algo") or "scrypt")
        except (TypeError, ValueError):
            return None
        if not salt:
            return None
        material = pin.strip().encode("utf-8")
        if algo == "pbkdf2_sha256" and hasattr(hashlib, "pbkdf2_hmac"):
            iterations = int(params.get("iterations", _PBKDF2_ITERATIONS))
            return hashlib.pbkdf2_hmac("sha256", material, salt, iterations, dklen=32)
        if algo == "scrypt" and hasattr(hashlib, "scrypt"):
            return hashlib.scrypt(
                material,
                salt=salt,
                n=int(params.get("n", _SCRYPT["n"])),
                r=int(params.get("r", _SCRYPT["r"])),
                p=int(params.get("p", _SCRYPT["p"])),
                dklen=32,
            )
        return None

    def verify_pin(self, role: str, pin: str) -> bool:
        entry = self._pin_entry(role)
        if not entry or not pin:
            return False
        digest = self._pin_digest(entry, str(pin))
        if digest is None:
            return False
        try:
            expected = bytes.fromhex(str(entry.get("hash") or ""))
        except ValueError:
            return False
        return bool(expected) and hmac.compare_digest(digest, expected)

    def pin_fingerprint(self, role: str) -> str:
        """Short, non-reversible marker of the current PIN.

        Sessions embed it, so rotating (or clearing) a PIN logs every existing
        session for that role out — no separate revocation list needed.
        """
        entry = self._pin_entry(role) or {}
        material = "{}:{}:{}".format(role, entry.get("salt", ""), entry.get("hash", ""))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    # -- sessions ---------------------------------------------------------
    def _session_secret(self) -> bytes:
        secret = self._data.get("session_secret")
        if not secret or not isinstance(secret, str):
            secret = secrets.token_urlsafe(32)
            self._data["session_secret"] = secret
            self._save()
        return secret.encode("utf-8")

    def issue_session(self, role: str, ttl: int = SESSION_TTL) -> Dict[str, Any]:
        role = (role or "").strip().lower()
        if role not in PIN_ROLES:
            raise ValueError("role must be one of {}".format(", ".join(PIN_ROLES)))
        expires = int(time.time()) + int(ttl)
        payload = "{}.{}.{}".format(role, expires, self.pin_fingerprint(role))
        signature = hmac.new(
            self._session_secret(), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return {
            "value": "{}.{}".format(payload, signature),
            "role": role,
            "expiresAt": expires,
            "maxAge": int(ttl),
        }

    def read_session(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        parts = str(value).split(".")
        if len(parts) != 4:
            return None
        role, expires_raw, fingerprint, signature = parts
        if role not in PIN_ROLES:
            return None
        try:
            expires = int(expires_raw)
        except ValueError:
            return None
        if expires <= int(time.time()):
            return None
        if not hmac.compare_digest(fingerprint, self.pin_fingerprint(role)):
            return None
        payload = "{}.{}.{}".format(role, expires, fingerprint)
        expected = hmac.new(
            self._session_secret(), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return role

    # -- info -------------------------------------------------------------
    def info(self, host: str, port: int) -> Dict[str, object]:
        tokens = self.tokens()
        display_host = "127.0.0.1" if host in ("127.0.0.1", "::1", "localhost", "0.0.0.0") else host
        ips = lan_ips()
        primary = ips[0] if ips else display_host
        base = "http://{}:{}".format(primary, port)
        return {
            "enabled": True,
            "host": display_host,
            "port": port,
            "lanIps": ips,
            "editorToken": tokens["editor"],
            "viewerToken": tokens["viewer"],
            "editorUrl": "{}?token={}".format(base, tokens["editor"]),
            "viewUrl": "{}?token={}".format(base, tokens["viewer"]),
            "pins": self.pins_configured(),
            "sessionTtlSeconds": SESSION_TTL,
            "note": (
                "Loopback access stays open. Remote visitors pick a role and enter its PIN; "
                "the older ?token= links keep working."
            ),
        }
