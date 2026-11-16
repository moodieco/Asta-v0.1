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

import json
import os
import secrets
import socket
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional


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
        self._data: Dict[str, str] = {}
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
            "note": "Loopback access stays open. Remote access requires one of these tokens.",
        }
