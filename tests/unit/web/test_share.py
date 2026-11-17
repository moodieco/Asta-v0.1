"""Share token issuance, authentication and regeneration."""

from __future__ import annotations

from pathlib import Path

import pytest

from asta.web.share import SESSION_TTL, ShareManager


def test_tokens_generated_distinct_and_persisted(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    tokens = manager.tokens()
    assert tokens["editor"]
    assert tokens["viewer"]
    assert tokens["editor"] != tokens["viewer"]
    assert (tmp_path / "share.json").is_file()

    # a fresh manager reads the same persisted tokens
    reloaded = ShareManager(tmp_path / "share.json")
    assert reloaded.tokens() == tokens


def test_authenticate_maps_roles(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    tokens = manager.tokens()
    assert manager.authenticate(tokens["editor"]) == "editor"
    assert manager.authenticate(tokens["viewer"]) == "viewer"
    assert manager.authenticate("not-a-token") is None
    assert manager.authenticate(None) is None


def test_regenerate_rotates_both_tokens(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    before = manager.tokens()
    manager.regenerate()
    after = manager.tokens()
    assert after["editor"] != before["editor"]
    assert after["viewer"] != before["viewer"]


def test_info_builds_urls(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    info = manager.info("127.0.0.1", 4310)
    assert info["enabled"] is True
    assert info["editorUrl"].startswith("http://")
    assert "?token=" in info["editorUrl"]
    assert "?token=" in info["viewUrl"]
    assert info["viewerToken"] != info["editorToken"]


# -- role PINs -------------------------------------------------------------


def test_pin_is_hashed_not_stored_in_the_clear(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    manager.set_pin("viewer", "555001")

    raw = (tmp_path / "share.json").read_text(encoding="utf-8")
    assert "555001" not in raw
    assert "scrypt" in raw or "pbkdf2_sha256" in raw
    assert manager.pin_configured("viewer") is True
    assert manager.pin_configured("editor") is False
    assert manager.verify_pin("viewer", "555001") is True
    assert manager.verify_pin("viewer", "000000") is False


def test_a_pin_only_unlocks_its_own_role(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    manager.set_pin("viewer", "555001")
    manager.set_pin("editor", "777003")
    assert manager.verify_pin("viewer", "777003") is False
    assert manager.verify_pin("editor", "555001") is False
    assert manager.verify_pin("editor", "777003") is True


def test_short_pins_and_unknown_roles_are_rejected(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    with pytest.raises(ValueError):
        manager.set_pin("admin", "123456")
    with pytest.raises(ValueError):
        manager.set_pin("viewer", "12")


def test_session_roundtrip_expiry_and_tampering(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    manager.set_pin("editor", "777003")

    session = manager.issue_session("editor")
    assert session["maxAge"] == SESSION_TTL
    assert manager.read_session(session["value"]) == "editor"

    expired = manager.issue_session("editor", ttl=-1)
    assert manager.read_session(expired["value"]) is None

    value = session["value"]
    tampered = value[:-4] + ("0000" if not value.endswith("0000") else "1111")
    assert manager.read_session(tampered) is None
    assert manager.read_session("editor.9999999999.deadbeef.nope") is None
    assert manager.read_session(None) is None


def test_rotating_a_pin_revokes_existing_sessions(tmp_path: Path) -> None:
    manager = ShareManager(tmp_path / "share.json")
    manager.set_pin("viewer", "555001")
    session = manager.issue_session("viewer")
    assert manager.read_session(session["value"]) == "viewer"

    manager.set_pin("viewer", "654321")
    assert manager.read_session(session["value"]) is None
    assert manager.verify_pin("viewer", "654321") is True
