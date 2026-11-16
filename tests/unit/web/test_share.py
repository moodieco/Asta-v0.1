"""Share token issuance, authentication and regeneration."""

from __future__ import annotations

from pathlib import Path

from asta.web.share import ShareManager


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
