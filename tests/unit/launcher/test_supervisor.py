"""Supervisor: pidfile truth, liveness, stopping something that is not running."""

from __future__ import annotations

import os
from pathlib import Path

from asta.launcher.supervisor import Supervisor


def test_status_when_nothing_runs(tmp_path: Path) -> None:
    supervisor = Supervisor(root=tmp_path, port=4399)
    status = supervisor.status()
    assert status["running"] is False
    assert status["pid"] is None
    assert status["url"].endswith(":4399/")


def test_pidfile_round_trip(tmp_path: Path) -> None:
    supervisor = Supervisor(root=tmp_path, port=4399)
    supervisor._write_pid(os.getpid())
    assert supervisor.read_pid() == os.getpid()
    assert supervisor._alive(os.getpid()) is True
    supervisor._clear_pid()
    assert supervisor.read_pid() is None


def test_stale_pidfile_is_not_reported_as_running(tmp_path: Path) -> None:
    supervisor = Supervisor(root=tmp_path, port=4399)
    # pid 999999 is virtually guaranteed to be unused
    supervisor._write_pid(999999)
    status = supervisor.status()
    assert status["pidAlive"] is False
    assert status["running"] is False


def test_stop_without_process_is_a_noop(tmp_path: Path) -> None:
    supervisor = Supervisor(root=tmp_path, port=4399)
    result = supervisor.stop(timeout=1)
    assert result["stopped"] is False
    assert result["reason"] == "not running"


def test_tail_log_reads_last_lines(tmp_path: Path) -> None:
    supervisor = Supervisor(root=tmp_path, port=4399)
    supervisor.logs_dir.mkdir(parents=True, exist_ok=True)
    supervisor.log_path.write_text("\n".join("line {}".format(i) for i in range(10)), encoding="utf-8")
    assert supervisor.tail_log(3) == ["line 7", "line 8", "line 9"]


def test_tail_log_missing_file_is_empty(tmp_path: Path) -> None:
    assert Supervisor(root=tmp_path, port=4399).tail_log(5) == []
