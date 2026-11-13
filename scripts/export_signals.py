"""Export stored signals to a spreadsheet (CSV or Google Sheets).

    PYTHONPATH=src python scripts/export_signals.py                 # use config/sheets.yaml
    PYTHONPATH=src python scripts/export_signals.py --out ~/Desktop/asta.csv
    PYTHONPATH=src python scripts/export_signals.py --dry-run       # show what would be added
    PYTHONPATH=src python scripts/export_signals.py --reset-cursor  # re-export everything
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.bootstrap import AstaApp  # noqa: E402
from asta.integrations.sheets.base import signal_to_row  # noqa: E402
from asta.integrations.sheets.csv_writer import CsvSheetWriter  # noqa: E402
from asta.utils.logger import configure_logging  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export ASTA signals to a spreadsheet")
    parser.add_argument("--config", default=None, help="config directory")
    parser.add_argument("--out", default=None, help="CSV path override (forces the csv driver)")
    parser.add_argument("--dry-run", action="store_true", help="print rows instead of writing")
    parser.add_argument("--reset-cursor", action="store_true", help="export from the first signal")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="clear the target sheet/file and re-export everything",
    )
    parser.add_argument("--limit", type=int, default=0, help="max rows to export this run")
    parser.add_argument("--rewrite", action="store_true", help="rewrite the whole target")
    args = parser.parse_args()

    configure_logging("WARNING")
    app = AstaApp.from_config(args.config).build()
    if app.sheet_sync is None:
        print("sheets export is disabled (config/sheets.yaml: enabled: false)")
        return 2

    if args.out:
        app.sheet_sync.writer = CsvSheetWriter(Path(args.out).expanduser())
    if args.reset_cursor:
        app.sheet_sync.state_path.unlink(missing_ok=True)
    if args.reset:
        app.sheet_sync.state_path.unlink(missing_ok=True)
        app.sheet_sync.writer.clear()

    if args.dry_run:
        records = app.history.recorded_after(
            app.sheet_sync.status()["last_recorded_at"] or None, args.limit or 20
        )
        print(json.dumps({"pending": len(records), "rows": [signal_to_row(r) for r in records]}, indent=2))
        app.close()
        return 0

    result = app.sheet_sync.rewrite_all() if args.rewrite else app.sync_sheet()
    print(json.dumps({"sync": result, "status": app.sheet_sync.status()}, indent=2))
    app.close()
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
