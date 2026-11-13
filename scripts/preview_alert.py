"""Render a sample Discord alert payload without sending it.

    PYTHONPATH=src python scripts/preview_alert.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from asta.core.signal_model import Market, Signal, SignalType
from asta.integrations.discord.embed_builder import build_payload


def main() -> int:
    signal = Signal(
        scanner_id="CXS002_VOLUME_SPIKE",
        scanner_name="Volume Spike",
        market=Market.CRYPTO,
        symbol="BTCUSDT",
        timeframe="15m",
        signal_type=SignalType.LONG,
        reason="Volume spike 5.2x the 20-bar average on a bullish candle (+3.00% body, 98% of range).",
        confidence=0.88,
        price=104250.5,
        timestamp=datetime.now(timezone.utc),
        strategy="Volume Spike",
        indicators={"volume_ratio": 5.2, "body_ratio": 0.98, "move_pct": 3.0},
    )
    print(json.dumps(build_payload(signal), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
