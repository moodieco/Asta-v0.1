"""Secrets: merge order, permissions, masking."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from asta.setup.secrets import is_configured, mask, read_env, render_env, write_env


def test_render_preserves_comments_and_order() -> None:
    existing = "\n".join(
        [
            "# comment at the top",
            "DISCORD_WEBHOOK_FOREX=https://discord.com/api/webhooks/1/old",
            "",
            "MT5_TERMINAL_URL=http://127.0.0.1:22346/mcp",
            "# trailing note",
        ]
    )
    body = render_env(existing, {"DISCORD_WEBHOOK_FOREX": "https://discord.com/api/webhooks/1/new"})
    lines = body.splitlines()
    assert lines[0] == "# comment at the top"
    assert lines[3] == "MT5_TERMINAL_URL=http://127.0.0.1:22346/mcp"
    assert lines[-1] == "# trailing note"
    assert "DISCORD_WEBHOOK_FOREX=https://discord.com/api/webhooks/1/new" in lines


def test_render_appends_missing_keys() -> None:
    body = render_env("A=1\n", {"B": "two words", "C": "3"})
    assert "A=1" in body
    assert 'B="two words"' in body
    assert "C=3" in body


def test_write_env_is_0600_and_round_trips(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    write_env(target, {"DISCORD_WEBHOOK_CRYPTO": "https://discord.com/api/webhooks/9/abc"})
    mode = stat.S_IMODE(os.stat(target).st_mode)
    assert mode == 0o600
    assert read_env(target)["DISCORD_WEBHOOK_CRYPTO"].endswith("/abc")

    write_env(target, {"MT5_TERMINAL_URL": "http://127.0.0.1:1/mcp"})
    values = read_env(target)
    assert "DISCORD_WEBHOOK_CRYPTO" in values
    assert values["MT5_TERMINAL_URL"] == "http://127.0.0.1:1/mcp"


def test_masking_hides_the_token() -> None:
    assert mask("https://discord.com/api/webhooks/123/abcdefghijklmnop").endswith("mnop")
    assert "discord" not in mask("https://discord.com/api/webhooks/123/abcdefghijklmnop")
    assert mask("short") == "•" * 5
    assert mask(None) == ""


def test_is_configured_rejects_placeholders() -> None:
    assert is_configured("https://discord.com/api/webhooks/1/x")
    assert not is_configured("")
    assert not is_configured("your-local-mcp-token")
