"""Setup state marker: idempotent, secret-free."""

from __future__ import annotations

import json
from pathlib import Path

from asta.setup.state import SetupState


def test_absent_state_is_not_complete(tmp_path: Path) -> None:
    state = SetupState.load(tmp_path / "setup_state.json")
    assert state.complete is False
    assert state.completed_steps() == []


def test_steps_and_completion_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "setup_state.json"
    state = SetupState.load(path)
    state.record_step("discord", {"configured": ["crypto"]})
    state.record_step("scanners", {"enabled": ["CXS001_RSI_DIVERGENCE"]})
    state.mark_complete({"port": "4310"})

    reloaded = SetupState.load(path)
    assert reloaded.complete is True
    assert reloaded.completed_steps() == ["discord", "scanners"]
    assert reloaded.step("discord")["configured"] == ["crypto"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["summary"]["port"] == "4310"
    assert "discord" in payload["steps"]


def test_reset_clears_everything(tmp_path: Path) -> None:
    path = tmp_path / "setup_state.json"
    state = SetupState.load(path)
    state.mark_complete({"port": "4310"})
    state.reset()
    assert SetupState.load(path).complete is False
