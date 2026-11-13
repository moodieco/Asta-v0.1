"""Google Sheets writer (Sheets API v4 over plain httpx).

Auth: an OAuth token file written by the Google Workspace setup (default
``~/.hermes/google_token.json``). Access tokens are refreshed on demand, so the
file only needs a ``refresh_token`` + client credentials.

REST reference:
  POST https://oauth2.googleapis.com/token                  (refresh)
  POST https://sheets.googleapis.com/v4/spreadsheets         (create)
  GET  .../v4/spreadsheets/{id}/values/{range}              (read header)
  POST .../v4/spreadsheets/{id}/values/{range}:append       (append)
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from asta.integrations.sheets.base import HEADER, SheetWriter
from asta.utils.exceptions import SheetsError
from asta.utils.logger import get_logger

TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_BASE = "https://sheets.googleapis.com/v4"
DRIVE_BASE = "https://www.googleapis.com/drive/v3"
SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)
SCOPES_SERVICE_ACCOUNT = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


class GoogleSheetsAuth:
    """Loads an OAuth token file and refreshes the access token when needed."""

    def __init__(
        self,
        token_path: Path,
        client: Optional[httpx.Client] = None,
        token_url: str = TOKEN_URL,
    ):
        self.token_path = Path(token_path).expanduser()
        self._client = client
        self._owns_client = client is None
        self.token_url = token_url
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self.logger = get_logger("asta.sheets.auth")

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=20)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    def load(self) -> Dict[str, Any]:
        if not self.token_path.exists():
            raise SheetsError(
                "Google token not found at {}. Run the Google Workspace OAuth setup "
                "(see docs/SPREADSHEET_SYNC.md) or switch sheets.driver to csv.".format(
                    self.token_path
                )
            )
        try:
            return json.loads(self.token_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SheetsError("token file is not valid JSON: {}".format(exc)) from exc

    def access_token(self, force_refresh: bool = False) -> str:
        if self._token and not force_refresh and time.time() < self._expires_at - 60:
            return self._token
        data = self.load()
        token = data.get("token") or data.get("access_token")
        expiry = data.get("expiry") or data.get("expires_at")
        if token and not force_refresh and self._expiry_from(expiry) > time.time() + 60:
            self._token = token
            self._expires_at = self._expiry_from(expiry)
            return token
        return self._refresh(data)

    def _refresh(self, data: Dict[str, Any]) -> str:
        refresh_token = data.get("refresh_token")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        if not (refresh_token and client_id and client_secret):
            raise SheetsError(
                "token file lacks refresh_token/client_id/client_secret; "
                "re-run the Google Workspace OAuth setup"
            )
        response = self.client.post(
            self.token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if response.status_code >= 400:
            raise SheetsError(
                "token refresh failed (HTTP {}): {}".format(
                    response.status_code, response.text[:200]
                )
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise SheetsError("token refresh returned no access_token")
        self._token = token
        self._expires_at = time.time() + float(payload.get("expires_in", 3600))
        self.logger.info("google access token refreshed")
        return token

    @staticmethod
    def _expiry_from(value: Any) -> float:
        if not value:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()


class GoogleServiceAccountAuth:
    """Auth from a service-account JSON key (server-to-server, no browser)."""

    def __init__(self, key_path: Path, scopes=SCOPES_SERVICE_ACCOUNT):
        self.key_path = Path(key_path).expanduser()
        self.scopes = tuple(scopes)
        self._credentials = None
        self.logger = get_logger("asta.sheets.service_account")

    def _build(self):
        if not self.key_path.exists():
            raise SheetsError(
                "service account key not found at {} (set sheets.service_account_path)".format(
                    self.key_path
                )
            )
        try:
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise SheetsError(
                "google-auth is required for service accounts: pip install 'asta[sheets]'"
            ) from exc
        credentials = service_account.Credentials.from_service_account_file(
            str(self.key_path), scopes=self.scopes
        )
        self._credentials = credentials
        return credentials

    def access_token(self, force_refresh: bool = False) -> str:
        from google.auth.transport.requests import Request

        credentials = self._credentials or self._build()
        if force_refresh or not credentials.valid:
            credentials.refresh(Request())
        if not credentials.token:
            raise SheetsError("service account did not return a token")
        return credentials.token

    def close(self) -> None:
        self._credentials = None


class GoogleDriveSharer:
    """Shares a spreadsheet owned by the service account with a real user."""

    def __init__(self, auth, base_url: str = DRIVE_BASE, client: Optional[httpx.Client] = None):
        self.auth = auth
        self.base_url = base_url.rstrip("/")
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=20)
            self._owns_client = True
        return self._client

    def share(self, file_id: str, email: str, role: str = "writer", notify: bool = False) -> Dict[str, Any]:
        token = self.auth.access_token()
        response = self.client.post(
            "{}/files/{}/permissions".format(self.base_url, file_id),
            headers={"Authorization": "Bearer {}".format(token)},
            params={"sendNotificationEmail": str(bool(notify)).lower()},
            json={"type": "user", "role": role, "emailAddress": email},
        )
        if response.status_code >= 400:
            raise SheetsError(
                "drive share failed (HTTP {}): {}".format(response.status_code, response.text[:200])
            )
        return response.json() if response.content else {}

    def close(self) -> None:
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None


class GoogleSheetsWriter(SheetWriter):
    name = "google"

    def __init__(
        self,
        auth: GoogleSheetsAuth,
        spreadsheet_id: str = "",
        sheet_name: str = "Signals",
        create_if_missing: bool = True,
        title: str = "ASTA Signals",
        client: Optional[httpx.Client] = None,
        base_url: str = SHEETS_BASE,
    ):
        self.auth = auth
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.create_if_missing = create_if_missing
        self.title = title
        self._client = client
        self._owns_client = client is None
        self.base_url = base_url.rstrip("/")
        self.logger = get_logger("asta.sheets.google")
        self._ready = False

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=20)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        self.auth.close()
        if self._client is not None and self._owns_client:
            self._client.close()
        self._client = None

    # -- API --------------------------------------------------------------
    def _request(
        self, method: str, url: str, token: str, **kwargs: Any
    ) -> Dict[str, Any]:
        response = self.client.request(
            method, url, headers={"Authorization": "Bearer {}".format(token)}, **kwargs
        )
        if response.status_code == 401:
            token = self.auth.access_token(force_refresh=True)
            response = self.client.request(
                method, url, headers={"Authorization": "Bearer {}".format(token)}, **kwargs
            )
        if response.status_code >= 400:
            raise SheetsError(
                "sheets API HTTP {}: {}".format(response.status_code, response.text[:300])
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    def create_spreadsheet(self, title: Optional[str] = None) -> str:
        token = self.auth.access_token()
        payload = {
            "properties": {"title": title or self.title},
            "sheets": [{"properties": {"title": self.sheet_name}}],
        }
        try:
            data = self._request(
                "POST", "{}/spreadsheets".format(self.base_url), token, json=payload
            )
        except SheetsError as exc:
            if "storage quota" in str(exc).lower() or "permission" in str(exc).lower():
                raise SheetsError(
                    "service accounts cannot create Drive files (no storage quota). "
                    "Create a Google Sheet yourself, share it with the service account email "
                    "as Editor, then put its id in config/sheets.yaml: spreadsheet_id."
                ) from exc
            raise
        spreadsheet_id = data.get("spreadsheetId")
        if not spreadsheet_id:
            raise SheetsError("create spreadsheet returned no id")
        self.spreadsheet_id = spreadsheet_id
        self.logger.info("spreadsheet created", extra={"spreadsheet_id": spreadsheet_id})
        return spreadsheet_id

    @property
    def _range(self) -> str:
        return "{}!A1".format(self.sheet_name)

    def sheet_titles(self) -> List[str]:
        token = self.auth.access_token()
        data = self._request(
            "GET",
            "{}/spreadsheets/{}".format(self.base_url, self.spreadsheet_id),
            token,
            params={"fields": "sheets.properties.title"},
        )
        return [
            (sheet.get("properties") or {}).get("title", "")
            for sheet in data.get("sheets") or []
        ]

    def add_sheet_tab(self, title: str) -> None:
        token = self.auth.access_token()
        self._request(
            "POST",
            "{}/spreadsheets/{}:batchUpdate".format(self.base_url, self.spreadsheet_id),
            token,
            json={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        )
        self.logger.info("sheet tab created", extra={"tab": title})

    def ensure_ready(self) -> None:
        if self._ready:
            return
        if not self.spreadsheet_id:
            if not self.create_if_missing:
                raise SheetsError("sheets.spreadsheet_id is empty and create_if_missing is false")
            self.create_spreadsheet()
        if self.sheet_name not in self.sheet_titles():
            self.add_sheet_tab(self.sheet_name)
        token = self.auth.access_token()
        existing = self._request(
            "GET",
            "{}/spreadsheets/{}/values/{}".format(
                self.base_url, self.spreadsheet_id, quote(self._range, safe="")
            ),
            token,
            params={"majorDimension": "ROWS"},
        )
        values = existing.get("values") or []
        self._ready = True
        if not values:
            self._append_rows([HEADER])
        return None

    def append_rows(self, rows: List[List[Any]]) -> int:
        if not rows:
            return 0
        self.ensure_ready()
        return self._append_rows(rows)

    def clear(self) -> None:
        """Wipe the data range (keeps the tab, drops the rows)."""
        token = self.auth.access_token()
        self._request(
            "POST",
            "{}/spreadsheets/{}/values/{}:clear".format(
                self.base_url,
                self.spreadsheet_id,
                quote("{}!A1:Z100000".format(self.sheet_name), safe=""),
            ),
            token,
            json={},
        )
        self._ready = False

    def replace_all(self, rows: List[List[Any]]) -> int:
        """Rewrite the tab (used after header changes or outcome updates)."""
        self.ensure_ready()
        token = self.auth.access_token()
        # clearing only "A1" would leave stale rows below: clear the whole tab
        whole_sheet = quote(self.sheet_name, safe="")
        sheet_range = quote("{}!A1".format(self.sheet_name), safe="")
        self._request(
            "POST",
            "{}/spreadsheets/{}/values/{}:clear".format(
                self.base_url, self.spreadsheet_id, whole_sheet
            ),
            token,
            json={},
        )
        self._request(
            "PUT",
            "{}/spreadsheets/{}/values/{}".format(
                self.base_url, self.spreadsheet_id, sheet_range
            ),
            token,
            params={"valueInputOption": "RAW"},
            json={"majorDimension": "ROWS", "values": rows},
        )
        self._ready = True
        return len(rows)

    def _append_rows(self, rows: List[List[Any]]) -> int:
        if not self.spreadsheet_id:
            raise SheetsError("no spreadsheet id configured")
        token = self.auth.access_token()
        url = "{}/spreadsheets/{}/values/{}:append".format(
            self.base_url, self.spreadsheet_id, quote("{}!A1".format(self.sheet_name), safe="")
        )
        payload = {"majorDimension": "ROWS", "values": rows}
        self._request(
            "POST",
            url,
            token,
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json=payload,
        )
        return len(rows)
