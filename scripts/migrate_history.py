"""Migrate the JSONL signal history into SQLite (idempotent).

    PYTHONPATH=src python scripts/migrate_history.py
    PYTHONPATH=src python scripts/migrate_history.py --source data/history/signals.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.config import load_config  # noqa: E402
from asta.core.signal_model import Signal  # noqa: E402
from asta.storage.database import Database  # noqa: E402
from asta.storage.repositories.signal_repository import SignalRepository  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="JSONL -> SQLite history migration")
    parser.add_argument("--config", default=None)
    parser.add_argument("--source", default=None, help="JSONL path (default: config value)")
    parser.add_argument("--target", default=None, help="SQLite path (default: config value)")
    args = parser.parse_args()

    configure_logging("WARNING")
    config = load_config(args.config)
    source = (
        Path(args.source)
        if args.source
        else config.resolve_path(config.storage.signal_history_path)
    )
    target = (
        Path(args.target) if args.target else config.resolve_path(config.storage.sqlite_path)
    )

    if not source.exists():
        print("no JSONL history at {}".format(source))
        return 0

    repository = SignalRepository(Database(target))
    before = repository.count()
    imported = 0
    skipped = 0
    for line in source.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            signal = Signal(
                scanner_id=record["scanner_id"],
                scanner_name=record["scanner_name"],
                market=record["market"],
                symbol=record["symbol"],
                timeframe=record["timeframe"],
                signal_type=record["signal_type"],
                reason=record["reason"],
                confidence=record["confidence"],
                price=record.get("price"),
                timestamp=record["timestamp"],
                strategy=record.get("strategy", ""),
                indicators=record.get("indicators") or {},
                metadata=record.get("metadata") or {},
            )
        except (KeyError, ValueError, TypeError) as exc:
            skipped += 1
            print("  skipped malformed line: {}".format(exc))
            continue
        imported += 1 if repository.save(signal) else 0

    print(
        json.dumps(
            {
                "source": str(source),
                "target": str(target),
                "imported": imported,
                "rows_before": before,
                "rows_now": repository.count(),
                "skipped_lines": skipped,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
