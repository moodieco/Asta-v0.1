"""Launcher panel API: status, setup context, validation, save, POST guard."""

from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from asta.launcher.control import PanelRoutes, PanelServer
from asta.launcher.supervisor import Supervisor

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    for name in ("app.yaml", "markets.yaml", "logging.yaml", "discord.yaml"):
        shutil.copy(REPO / "config" / name, config / name)
    (tmp_path / ".env").write_text(
        "DISCORD_WEBHOOK_CRYPTO=https://discord.com/api/webhooks/1/abcdefghijkl\n", encoding="utf-8"
    )
    return tmp_path


def _routes(project: Path) -> PanelRoutes:
    supervisor = Supervisor(root=project, port=4397)
    return PanelRoutes(supervisor, config_dir=str(project / "config"))


def test_status_shape(project: Path) -> None:
    payload = _routes(project).status()
    assert payload["supervisor"]["running"] is False
    assert payload["setupComplete"] is False
    assert payload["config"]["root"] == str(project)


def test_setup_context_masks_secrets(project: Path) -> None:
    context = _routes(project).setup_context()
    crypto = context["webhooks"]["crypto"]
    assert crypto["configured"] is True
    assert "discord.com" not in crypto["masked"]
    assert crypto["masked"].endswith("ijkl")
    assert context["webhooks"]["forex"]["configured"] is False
    # one entry per built-in scanner package; keep this in sync when adding one
    assert len(context["scanners"]) == 10
    assert "FXS003_ASIA_RANGE_BREAKOUT" in {scanner["id"] for scanner in context["scanners"]}
    assert context["system"]["port"] == 4310


def test_save_writes_env_yaml_and_state(project: Path) -> None:
    routes = _routes(project)
    result = routes.save_setup(
        {
            "webhooks": {"forex": "https://discord.com/api/webhooks/2/zyxwvutsrqpo"},
            "mt5": {"url": "http://127.0.0.1:22346/mcp", "token": "tok"},
            "scanners": {"CXS002_VOLUME_SPIKE": False},
            "system": {"dbPath": "data/history/asta.db", "host": "127.0.0.1", "port": 4321},
        }
    )
    assert result["saved"] is True

    env = (project / ".env").read_text(encoding="utf-8")
    assert "DISCORD_WEBHOOK_FOREX" in env and "zyxwvutsrqpo" in env
    assert "MT5_TERMINAL_URL" in env
    assert oct((project / ".env").stat().st_mode & 0o777) == "0o600"

    app = yaml.safe_load((project / "config" / "app.yaml").read_text(encoding="utf-8"))
    assert app["web"]["port"] == 4321

    markets = yaml.safe_load((project / "config" / "markets.yaml").read_text(encoding="utf-8"))
    assert markets["scanner_overrides"]["CXS002_VOLUME_SPIKE"]["enabled"] is False

    state = json.loads((project / "config" / "setup_state.json").read_text(encoding="utf-8"))
    assert state["completed_at"]
    assert "abcdefghijkl" not in json.dumps(state)  # no secrets in the marker


def test_http_roundtrip_and_post_guard(project: Path) -> None:
    panel = PanelServer(Supervisor(root=project, port=4397), port=0, config_dir=str(project / "config"))
    url = panel.start().rstrip("/")
    try:
        with urllib.request.urlopen(url + "/api/launcher/status", timeout=5) as response:
            assert json.loads(response.read())["config"]["root"] == str(project)

        with urllib.request.urlopen(url + "/", timeout=5) as response:
            assert b"panel.js" in response.read()

        request = urllib.request.Request(url + "/api/launcher/start", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(request, timeout=5)
        assert excinfo.value.code == 403

        request = urllib.request.Request(
            url + "/api/launcher/setup/validate",
            data=json.dumps({"system": {"port": 4397, "dbPath": "data/history/asta.db"}}).encode(),
            method="POST",
        )
        request.add_header("X-ASTA-Panel", "1")
        request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read())
        assert "results" in payload
        assert any(item["label"].startswith("Port") for item in payload["results"]["local"])
    finally:
        panel.stop()
